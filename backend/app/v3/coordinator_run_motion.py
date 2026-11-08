"""One physical actor/cart trace; planned ends remain separate from observed progress."""

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.coordinator_run_plans import Plans
from app.v3.coordinator_run_role_exposure import available
from app.v3.light_flow_models import FlowCartView, FlowEvent, FlowOperation
from app.v3.light_flow_state import CartState, HumanState
from app.v3.receipt_flow_plan import receipt_window
from app.v3.whole_flow_plan import outbound_window

ASSIGN = {"actor_assigned", "receipt_admitted", "whole_admitted", "role_transition_assigned"}
RELEASE = {
    "picker_returned",
    "parcel_shipper_returned",
    "receipt_returned",
    "whole_returned",
    "packing_actor_released",
    "role_activated",
    "role_restored",
}


class MotionJournal:
    def __init__(
        self, profile: CoordinatorProfile, inventory: InventoryJournal, horizon: int
    ) -> None:
        self.profile, self.inventory, self.horizon = profile, inventory, horizon
        self.plans = Plans(profile, inventory)
        flow, resources = profile.world.receipts.flow, profile.unit_resources
        self.workers = {a.actor_id: HumanState(a, a.home) for a in flow.actors}
        carts = tuple(c.cart for c in resources.carts) if resources else (flow.cart,)
        self.carts = {c.cart_id: CartState(c, c.home) for c in carts}
        self.cart_orders: dict[str, str] = {}
        self.completed: dict[tuple[str, str, int, str], FlowEvent] = {}
        self.role_states: dict[str, tuple[str, str]] = {}

    def apply(self, event: FlowEvent) -> None:
        if isinstance(event, CoordinatorEvent) and event.role_view is not None:
            role = event.role_view
            self.role_states[role.intent_id] = (role.actor_id, role.status)
        if event.kind == "packing_reserved":
            self._packing(event)
        if event.kind in ASSIGN:
            self._assign(event)
        elif event.kind == "operation_started":
            self._start(event)
        elif event.kind == "operation_completed":
            self._finish(event)
        elif event.kind in RELEASE:
            self._release(event)
        elif event.kind == "cart_released":
            self._release_cart(event)

    def _actor(self, event: FlowEvent) -> HumanState:
        if event.actor_id not in self.workers:
            raise ValueError("Physical event lacks a known actor")
        return self.workers[event.actor_id]

    def _packing(self, event: FlowEvent) -> None:
        if not isinstance(event, CoordinatorEvent) or event.packing is None:
            raise ValueError("Packing reservation lacks its native binding")
        actor = self.workers.get(event.packing.actor_id)
        if actor is None or actor.node is None or actor.order_id is not None:
            raise ValueError("Packing actor is not physically free")
        self.plans.packing(event, actor.node)

    def _assign(self, event: FlowEvent) -> None:
        worker = self._actor(event)
        if worker.operation is not None or worker.order_id not in (None, event.order_id):
            raise ValueError("Actor assignment overlaps existing work")
        if worker.order_id is None:
            self._eligible(event)
        if event.kind == "role_transition_assigned":
            self.plans.role_assigned(event.order_id, worker.spec.actor_id)
        worker.order_id, worker.waiting_since = event.order_id, event.tick
        view = self.inventory.views.get(event.order_id)
        packing = self.plans.current.get((event.order_id, worker.spec.actor_id)) == "packing"
        if view is not None and event.actor_id == view.picker_id and not packing:
            cart = self.carts[view.cart.cart_id]
            if cart.node != view.cart.home or view.cart.cart_id in self.cart_orders:
                raise ValueError("Picker assignment requires the actual returned free cart")
            self.cart_orders[view.cart.cart_id] = event.order_id

    def _eligible(self, event: FlowEvent) -> None:
        actor = self._actor(event).spec.actor_id
        if not available(self.profile, actor, event.tick):
            raise ValueError("New physical assignment starts outside actor availability")
        if event.kind == "role_transition_assigned":
            return
        active = [
            phase
            for owner, phase in self.role_states.values()
            if owner == actor and phase not in {"unreleased", "restored", "rejected"}
        ]
        capability = next(w for w in self.profile.registry.workers if w.actor_id == actor)
        actual = "pack" if active == ["active"] else capability.primary_role
        if active and active != ["active"]:
            raise ValueError("Assigned actor has not completed its actual role transition")
        role = "receive" if event.order_id in self.inventory.receipts else "ship"
        if event.order_id in self.inventory.units:
            view = self.inventory.views[event.order_id]
            packing = self.plans.current.get((event.order_id, actor)) == "packing"
            role = "pack" if packing else "pick" if actor == view.picker_id else "ship"
        if actual != role or role not in capability.eligible_roles:
            raise ValueError("Physical assignment lacks actual effective role and declared skill")

    def _start(self, event: FlowEvent) -> None:
        worker, operation = self._actor(event), event.operation
        if worker.operation is not None:
            raise ValueError("Physical actor operations overlap")
        if operation is None or worker.node is None or worker.order_id != event.order_id:
            raise ValueError("Operation lacks actual assigned actor position")
        step = self.plans.expected(event, worker.spec.actor_id, worker.node)
        expected = FlowOperation(
            step.kind,
            event.order_id,
            event.tick,
            event.tick + step.duration,
            worker.node,
            step.target,
            step.route,
            step.carrying_id,
            step.cart_id,
        )
        same(operation, expected, "Operation differs from its declared physical plan")
        self._window(event)
        worker.stop_waiting(event.tick)
        worker.operation = operation
        if operation.cart_id is not None:
            cart = self.carts[operation.cart_id]
            if cart.node != worker.node or cart.operation is not None:
                raise ValueError("Cart operation overlaps or teleports to its actor")
            cart.operation = operation
            if operation.route is not None:
                cart.node = None
        if operation.route is not None:
            worker.node = None

    def _window(self, event: FlowEvent) -> None:
        operation = event.operation
        if operation is None:
            raise ValueError("Service window requires an actual operation")
        duration, key = operation.planned_end_tick - event.tick, event.order_id
        if operation.kind == "receipt_service":
            offer = self.inventory.receipts[key]
            valid = receipt_window(
                self.inventory.receipt_ports[offer.port_id], event.tick, duration, self.horizon
            )
        elif operation.kind == "whole_service":
            order = self.inventory.whole[key]
            valid = outbound_window(self.inventory.whole_ports[order.port_id], event.tick, duration)
        elif operation.kind == "shipping_service":
            port = self.inventory.views[key].port
            valid = any(a <= event.tick < b and event.tick + duration <= b for a, b in port.windows)
        else:
            return
        if not valid:
            raise ValueError("Actual service violates its declared source deadline")

    def _finish(self, event: FlowEvent) -> None:
        worker, operation = self._actor(event), event.operation
        same(operation, worker.operation, "Completion differs from actual open operation")
        if operation is None or operation.planned_end_tick != event.tick:
            raise ValueError("Completion is not the actual planned end")
        worker.closed_paid += event.tick - operation.start_tick
        worker.node, worker.operation, worker.waiting_since = (
            operation.target_node,
            None,
            event.tick,
        )
        if operation.cart_id is not None:
            cart = self.carts[operation.cart_id]
            same(cart.operation, operation, "Cart completion differs from actual actor operation")
            cart.node, cart.operation = operation.target_node, None
        key = (event.order_id, operation.kind, event.tick, worker.spec.actor_id)
        if key in self.completed:
            raise ValueError("Duplicate actual operation completion")
        self.completed[key] = event

    def _release(self, event: FlowEvent) -> None:
        worker = self._actor(event)
        if worker.operation is not None or worker.order_id != event.order_id or worker.node is None:
            raise ValueError("Actor release precedes actual operation completion")
        if event.kind != "role_activated" and not self.plans.finished(
            event.order_id, worker.spec.actor_id, worker.node
        ):
            raise ValueError("Actor release skipped remaining declared paid steps")
        worker.stop_waiting(event.tick)
        worker.order_id = None

    def _release_cart(self, event: FlowEvent) -> None:
        view, worker = self.inventory.views[event.order_id], self._actor(event)
        cart = self.carts[view.cart.cart_id]
        if (
            event.actor_id != view.picker_id
            or worker.order_id != event.order_id
            or cart.operation is not None
            or cart.node != view.cart.home
            or worker.node != view.cart.home
            or self.cart_orders.get(view.cart.cart_id) != event.order_id
        ):
            raise ValueError("Cart release precedes actual paid return")
        del self.cart_orders[view.cart.cart_id]

    def check(self, state: CoordinatorSnapshot) -> None:
        for worker in self.workers.values():
            if (
                worker.order_id is not None
                and worker.node is not None
                and worker.operation is None
                and self.plans.finished(worker.order_id, worker.spec.actor_id, worker.node)
            ):
                raise ValueError("Finished physical actor lacks its immediate release fact")
            if (
                worker.operation is not None
                and worker.operation.kind == "picker_return"
                and worker.order_id in self.cart_orders.values()
            ):
                raise ValueError("Picker left a returned cart without its actual release fact")
        expected = tuple(w.view(state.tick) for _, w in sorted(self.workers.items()))
        same(state.workers, expected, "Captured actors differ from actual paid operation journal")
        carts = tuple(
            FlowCartView(k, c.node, c.operation, self.cart_orders.get(k))
            for k, c in sorted(self.carts.items())
        )
        same(state.carts, carts, "Captured carts differ from actual cart operations")
        default = self.profile.world.receipts.flow.cart.cart_id
        same(
            state.cart, next(c for c in carts if c.cart_id == default), "Default cart alias differs"
        )
