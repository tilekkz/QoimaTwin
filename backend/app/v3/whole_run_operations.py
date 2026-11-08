"""Actual whole handoffs require continuous declared operations and one shared actor clock."""

from app.v3.flow_profile_wire import record
from app.v3.interface import Json
from app.v3.light_flow_state import HumanStep
from app.v3.receipt_run_journal import InventoryJournal, same
from app.v3.stock_models import ContainerRecipe
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_flow_plan import whole_plan
from app.v3.whole_native_decode import decode


class WholeOperations:
    def __init__(self, profile: WholeFlowProfile, inventory: InventoryJournal) -> None:
        self.profile, self.inventory = profile, inventory
        self.actors = {a.actor_id: a for a in profile.receipts.flow.actors}
        self.nodes = {a.actor_id: a.home for a in self.actors.values()}
        self.active: dict[str, Json] = {}
        self.completed: dict[tuple[str, str, int], Json] = {}
        self.started: list[tuple[str, Json]] = []
        self.plans: dict[str, list[HumanStep]] = {}
        self.indices: dict[str, int] = {}
        self.orders = {o.job_id: o for o in profile.orders}
        self.assignment: dict[str, str] = {}

    def apply(self, event: Json, horizon: int) -> None:
        key, kind, actor = event["order_id"], event["kind"], event["actor_id"]
        if kind == "whole_admitted":
            self._admit(event, horizon)
        if kind == "operation_started":
            self._start(event)
        elif kind == "operation_completed":
            operation = event["operation"]
            same(
                operation,
                self.active.get(actor),
                "Actor completion lacks its actual open operation",
            )
            if event["tick"] != operation["planned_end_tick"]:
                raise ValueError("Actor completion differs from its actual planned end")
            self.nodes[actor] = operation["target_node"]
            del self.active[actor]
            self.completed[key, operation["kind"], event["tick"]] = event
        if kind == "whole_returned":
            if key not in self.plans or self.indices[key] != len(self.plans[key]):
                raise ValueError("Whole return skipped a declared paid operation")
            if actor in self.active or self.nodes.get(actor) != self.actors[actor].home:
                raise ValueError("Whole return is not actual idle arrival at home")
            if self.assignment.pop(actor, None) != key:
                raise ValueError("Whole return lost its shared actor assignment")

    def _admit(self, event: Json, horizon: int) -> None:
        key, view, actor = event["order_id"], event["whole_order"], event["actor_id"]
        order = self.orders[key]
        port = next(p for p in self.profile.ports if p.port_id == order.port_id)
        if view["buffer_owner_id"] not in port.buffer_ids:
            raise ValueError("Whole admitted buffer is not permitted by its selected port")
        if not order.arrival_tick <= event["tick"] < horizon or actor not in port.shipper_ids:
            raise ValueError("Whole admission is outside [arrival,H) or its declared actor pool")
        if actor in self.assignment or actor in self.active or key in self.plans:
            raise ValueError("Whole admission duplicates an actual job or occupied actor")
        spec = self.actors[actor]
        if event["tick"] < spec.available_tick or self.nodes[actor] != spec.home:
            raise ValueError("Whole admission violates actual actor availability/home")
        hu = self.inventory.containers[order.hu_id]
        places = {p.owner_id: p for p in self.profile.places}
        source, buffer = places[hu["owner_id"]], places[view["buffer_owner_id"]]
        recipes = {r["recipe_id"]: r for r in self.inventory.catalog["container_recipes"]}
        cargo = decode(ContainerRecipe, recipes[self.inventory.recipes[order.hu_id]])
        steps = whole_plan(self.profile, order, cargo, source, buffer, port, spec)
        self.plans[key] = [step for step in steps if step.duration]
        self.indices[key], self.assignment[actor] = 0, key

    def _start(self, event: Json) -> None:
        key, actor, operation, tick = (
            event[k] for k in ("order_id", "actor_id", "operation", "tick")
        )
        if actor not in self.actors or actor in self.active or operation is None:
            raise ValueError("Paid actor operation overlaps or has no declared actor")
        if actor in self.assignment and self.assignment[actor] != key:
            raise ValueError("Another job uses an exclusively assigned whole actor")
        if operation["order_id"] != key or operation["start_tick"] != tick:
            raise ValueError("Started operation job/clock differs")
        if operation["planned_end_tick"] <= tick or operation["source_node"] != self.nodes[actor]:
            raise ValueError(
                "Paid operation is nonpositive or teleports from actual actor position"
            )
        if key in self.orders:
            self._whole_start(event)
        self.active[actor] = operation
        self.started.append((actor, operation))

    def _whole_start(self, event: Json) -> None:
        key, op, tick = event["order_id"], event["operation"], event["tick"]
        if self.assignment.get(event["actor_id"]) != key:
            raise ValueError("Whole operation has no actual admitted actor")
        index = self.indices[key]
        if index >= len(self.plans[key]):
            raise ValueError("Whole operation exceeds its declared paid plan")
        step = self.plans[key][index]
        expected = {
            "kind": step.kind,
            "order_id": key,
            "start_tick": tick,
            "planned_end_tick": tick + step.duration,
            "source_node": self.nodes[event["actor_id"]],
            "target_node": step.target,
            "route": record(step.route),
            "carrying_id": step.carrying_id,
            "cart_id": step.cart_id,
        }
        same(op, expected, "Whole operation differs from exact directed geometry/service plan")
        if step.kind == "whole_service":
            port = next(p for p in self.profile.ports if p.port_id == self.orders[key].port_id)
            if not any(a <= tick < b and tick + step.duration <= b for a, b in port.windows):
                raise ValueError("Whole service exceeds its actual source port window")
        self.indices[key] += 1

    def handoff(self, event: Json, operation_kind: str) -> None:
        key = event["order_id"], operation_kind, event["tick"]
        completion = self.completed.get(key)
        if completion is None or completion["actor_id"] != event["actor_id"]:
            raise ValueError("Whole stock handoff lacks actual assigned operation completion")

    def check(self, state: Json, tick: int) -> None:
        for worker in state["workers"]:
            actor = worker["actor_id"]
            operation = self.active.get(actor)
            same(
                worker["operation"],
                operation,
                "Captured actor operation differs from actual journal",
            )
            node = (
                None
                if operation is not None and operation["route"] is not None
                else self.nodes[actor]
            )
            same(
                worker["node"], node, "Captured actor pose teleports from actual operation history"
            )
            paid = sum(
                max(0, min(tick, op["planned_end_tick"]) - op["start_tick"])
                for who, op in self.started
                if who == actor
            )
            same(
                worker["paid_ticks"],
                paid,
                "Captured paid labor differs from actual [0,T) operations",
            )
            if actor in self.assignment and worker["order_id"] != self.assignment[actor]:
                raise ValueError("Whole assigned actor was silently released before paid return")
