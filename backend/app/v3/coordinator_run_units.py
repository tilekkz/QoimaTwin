"""Mutable multi-station unit state is derived from declared bindings and completed stages."""

from dataclasses import replace

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorSnapshot
from app.v3.coordinator_packing_models import PackingView, UnitContext
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_resource_rules import packing_resources
from app.v3.coordinator_units_state import UnitProgress
from app.v3.light_flow_models import FlowEvent, FlowOrderView


class UnitJournal:
    def __init__(self, inventory: InventoryJournal, motion: MotionJournal) -> None:
        self.inventory, self.motion = inventory, motion
        self.orders = {key: FlowOrderView(key, "unreleased", None, None) for key in inventory.units}
        self.contexts: dict[str, UnitContext] = {}
        self.packing: dict[str, PackingView] = {}
        self.waits: dict[str, str] = {}
        self.marks: dict[tuple[str, str], int] = {}

    def apply(self, event: FlowEvent) -> None:
        if event.order_id not in self.orders:
            return
        key, kind = event.order_id, event.kind
        self._context(event)
        statuses = {
            "order_arrived": "waiting",
            "order_admitted": "picking",
            "intake_handoff": "belt",
            "packing_cleared": "belt_return",
            "output_ready": "output",
            "shipped": "shipped",
        }
        if kind in statuses:
            self.orders[key] = replace(self.orders[key], status=statuses[kind])
        if kind == "order_admitted":
            self.orders[key] = replace(self.orders[key], admitted_tick=event.tick)
        elif kind == "shipped":
            self.orders[key] = replace(self.orders[key], shipped_tick=event.tick)
        view = self.inventory.views[key]
        packing = self.motion.plans.current.get((key, str(event.actor_id))) == "packing"
        if kind == "actor_assigned" and event.actor_id == view.shipper_id and not packing:
            self.orders[key] = replace(self.orders[key], status="collecting")
        if kind in {
            "picked",
            "intake_handoff",
            "output_collected",
            "cart_released",
            "picker_returned",
            "parcel_shipper_returned",
        }:
            if (key, kind) in self.marks:
                raise ValueError("Unit physical milestone occurred twice")
            self.marks[key, kind] = event.tick
        self._packing(event)

    def _context(self, event: FlowEvent) -> None:
        key, view, order = (
            event.order_id,
            self.inventory.views[event.order_id],
            self.inventory.units[event.order_id],
        )
        expected = UnitContext(
            key,
            view.picker_id,
            view.cart.cart_id,
            view.station.station_id,
            view.shipper_id,
            order.source_node,
            view.intake_node,
            view.output_node,
            view.port.port_id,
        )
        if event.kind == "unit_context_bound":
            if key in self.contexts:
                raise ValueError("Duplicate immutable unit resource binding")
            self.contexts[key] = expected
        if isinstance(event, CoordinatorEvent):
            if event.unit_context is None or key not in self.contexts:
                raise ValueError("Unit event lacks its admitted exact physical context")
            same(
                event.unit_context, expected, "Unit event substituted its physical resource binding"
            )

    def _packing(self, event: FlowEvent) -> None:
        if not isinstance(event, CoordinatorEvent):
            return
        key, kind, supplied = event.order_id, event.kind, event.packing
        if kind == "packing_reserved":
            if supplied is None or key in self.packing:
                raise ValueError("Packing assignment missing or duplicated")
            self.packing[key] = PackingView(
                key,
                supplied.actor_id,
                self.inventory.views[key].station.station_id,
                supplied.role_intent_id,
                "approach",
                event.tick,
                None,
                None,
                None,
                packing_resources(self.inventory, event),
            )
            self.waits.pop(key, None)
        if kind == "packing_deferred":
            if event.packing_wait_reason is None:
                raise ValueError("Packing deferral lost its actual wait reason")
            self.waits[key] = event.packing_wait_reason
        if key in self.packing:
            self._packing_stage(event)

    def _packing_stage(self, event: CoordinatorEvent) -> None:
        key, kind = event.order_id, event.kind
        value, operation = self.packing[key], event.operation
        if event.actor_id == value.actor_id and operation is not None:
            if kind == "operation_started" and operation.kind in {"pack", "clear"}:
                value = replace(value, phase=operation.kind)
                self.orders[key] = replace(self.orders[key], status="packing")
            elif kind == "operation_completed" and operation.kind == "travel_empty":
                value = replace(value, phase="ready")
        if kind == "packed":
            value = replace(value, phase="packed", packed_tick=event.tick)
        elif kind == "packing_cleared":
            phase = "complete" if value.role_intent_id is not None else "returning"
            held = () if phase == "complete" else packing_resources(self.inventory, event)[:1]
            value = replace(value, phase=phase, cleared_tick=event.tick, held_resources=held)
        elif kind == "packing_actor_released":
            value = replace(value, phase="complete", released_tick=event.tick, held_resources=())
        self.packing[key] = value

    def _completed_steps(self, key: str, actor: str, category: str) -> int:
        identity = (key, actor, category)
        plans = self.motion.plans
        if identity not in plans.values:
            return 0
        index = plans.indices[identity]
        operation = self.motion.workers[actor].operation
        if (
            operation is not None
            and operation.order_id == key
            and plans.current.get((key, actor)) == category
        ):
            return index - 1
        steps = plans.values[identity]
        while index < len(steps) and steps[index].duration == 0:
            index += 1
        return index

    def _progress(self, key: str) -> UnitProgress:
        view = self.inventory.views[key]
        return UnitProgress(
            key,
            self._completed_steps(key, view.picker_id, "picker"),
            self.marks.get((key, "picked")),
            self.marks.get((key, "intake_handoff")),
            self.marks.get((key, "output_collected")),
            self.marks.get((key, "cart_released")),
            self.marks.get((key, "picker_returned")),
            self._completed_steps(key, view.shipper_id, "shipper"),
            self.marks.get((key, "parcel_shipper_returned")),
        )

    def progress(self) -> tuple[UnitProgress, ...]:
        """Return immutable current progress without duplicating plan arithmetic."""
        return tuple(self._progress(key) for key in sorted(self.contexts))

    def check(self, state: CoordinatorSnapshot) -> None:
        same(
            state.orders,
            tuple(self.orders[key] for key in sorted(self.orders)),
            "Unit orders differ",
        )
        same(
            state.unit_contexts,
            tuple(self.contexts[key] for key in sorted(self.contexts)),
            "Captured unit bindings differ",
        )
        same(
            state.packing,
            tuple(self.packing[key] for key in sorted(self.packing)),
            "Captured multi-station packing differs",
        )
        same(
            state.packing_waits, tuple(sorted(self.waits.items())), "Captured packing waits differ"
        )
        same(
            state.unit_progress,
            self.progress(),
            "Captured unit progress invents completed physical steps",
        )
        releases = tuple(
            (key, tick)
            for (key, kind), tick in sorted(self.marks.items())
            if kind == "cart_released"
        )
        same(state.cart_releases, releases, "Captured paid cart release facts differ")
