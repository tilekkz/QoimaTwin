"""Declared C human plans, independent of event-provided routes and future end times."""

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorProfile
from app.v3.coordinator_run_inventory import InventoryJournal
from app.v3.coordinator_units import picking_steps
from app.v3.coordinator_validation import role_route
from app.v3.light_flow_models import FlowEvent
from app.v3.light_flow_plan import shipper_plan, travel
from app.v3.light_flow_state import HumanStep
from app.v3.receipt_flow_plan import receipt_plan
from app.v3.whole_flow_plan import whole_plan


class Plans:
    def __init__(self, profile: CoordinatorProfile, inventory: InventoryJournal) -> None:
        self.profile, self.inventory = profile, inventory
        self.actors = {a.actor_id: a for a in profile.world.receipts.flow.actors}
        self.values: dict[tuple[str, str, str], list[HumanStep]] = {}
        self.indices: dict[tuple[str, str, str], int] = {}
        self.current: dict[tuple[str, str], str] = {}
        self.intents = {i.intent_id: i for i in profile.intents}

    def packing(self, event: CoordinatorEvent, node: str) -> None:
        packing = event.packing
        if packing is None or event.order_id not in self.inventory.views:
            raise ValueError("Packing reservation lacks a declared unit context")
        profile = self.inventory.views[event.order_id]
        actor = self.actors[packing.actor_id]
        steps = [
            travel(profile, actor, node, profile.station.node, "travel_empty"),
            HumanStep("pack", profile.station.node, profile.times.pack),
            HumanStep("clear", profile.station.node, profile.times.clear),
        ]
        if packing.role_intent_id is None:
            if actor.actor_id != profile.packer_id:
                raise ValueError("Primary packing actor differs from the declared station")
            steps.append(travel(profile, actor, profile.station.node, actor.home, "return"))
        else:
            intent = self.intents.get(packing.role_intent_id)
            if intent is None or (intent.actor_id, intent.station_id) != (
                actor.actor_id,
                profile.station.station_id,
            ):
                raise ValueError("Helper packing lacks its declared role intent")
        self._store((event.order_id, actor.actor_id, "packing"), steps)
        self.current[event.order_id, actor.actor_id] = "packing"

    def _store(self, key: tuple[str, str, str], steps: list[HumanStep]) -> None:
        if key in self.values:
            raise ValueError("Duplicate physical plan assignment")
        self.values[key], self.indices[key] = steps, 0

    def role_assigned(self, key: str, actor: str) -> None:
        identity = (key, actor, "role")
        if identity not in self.values:
            self._store(identity, self._role(key, actor))
        self.current[key, actor] = "role"

    def expected(self, event: FlowEvent, actor: str, node: str) -> HumanStep:
        pair = (event.order_id, actor)
        if pair not in self.current:
            self.current[pair] = self._category(event.order_id, actor)
        key = (*pair, self.current[pair])
        if key not in self.values:
            self._store(key, self._derive(event.order_id, actor))
        steps, index = self.values[key], self.indices[key]
        while index < len(steps) and steps[index].duration == 0:
            if steps[index].target != node:
                raise ValueError("Zero-length declared operation changes physical node")
            index += 1
        if index >= len(steps):
            raise ValueError("Operation continues after its declared physical plan")
        self.indices[key] = index + 1
        return steps[index]

    def _category(self, key: str, actor: str) -> str:
        if key in self.intents:
            return "role"
        if key in self.inventory.units:
            return "picker" if actor == self.inventory.views[key].picker_id else "shipper"
        return "receipt" if key in self.inventory.receipts else "whole"

    def _derive(self, key: str, actor: str) -> list[HumanStep]:
        if key in self.intents:
            return self._role(key, actor)
        if key in self.inventory.units:
            profile, spec = self.inventory.views[key], self.actors[actor]
            if actor == profile.picker_id:
                resources = self.profile.unit_resources
                release = (
                    next(
                        (
                            c.release_tick
                            for c in resources.carts
                            if c.cart.cart_id == profile.cart.cart_id
                        ),
                        0,
                    )
                    if resources
                    else 0
                )
                return picking_steps(profile, release)
            if actor == profile.shipper_id:
                return shipper_plan(profile, spec, self.inventory.units[key])
            raise ValueError("Unit operation lacks its declared picker/shipper/packing plan")
        return self._whole_or_receipt(key, actor)

    def _role(self, key: str, actor: str) -> list[HumanStep]:
        intent = self.intents[key]
        if actor != intent.actor_id:
            raise ValueError("Role operation has another actor")
        node = next(s.node_id for s in self.profile.stations if s.station_id == intent.station_id)
        outward, first = role_route(self.profile, actor, self.actors[actor].home, node)
        inward, last = role_route(self.profile, actor, node, intent.restore_node)
        return [
            HumanStep("role_outward", node, outward, first),
            HumanStep("role_return", intent.restore_node, inward, last),
        ]

    def _whole_or_receipt(self, key: str, actor: str) -> list[HumanStep]:
        if key not in self.inventory.assignments:
            raise ValueError("Human plan lacks an admitted physical assignment")
        assigned, buffer = self.inventory.assignments[key]
        if assigned != actor:
            raise ValueError("Human operation changes admitted actor")
        world, spec = self.profile.world, self.actors[actor]
        if key in self.inventory.receipts:
            offer = self.inventory.receipts[key]
            place = next(p for p in world.receipts.places if p.owner_id == buffer)
            return receipt_plan(
                world.receipts, offer, self.inventory.receipt_ports[offer.port_id], place, spec
            )
        order = self.inventory.whole[key]
        contents = self.inventory.ledger.contents(order.hu_id)
        source = next(p for p in world.places if p.owner_id == contents.container.owner_id)
        target = next(p for p in world.places if p.owner_id == buffer)
        return whole_plan(
            world,
            order,
            contents.container.recipe,
            source,
            target,
            self.inventory.whole_ports[order.port_id],
            spec,
        )

    def finished(self, key: str, actor: str, node: str) -> bool:
        identity = (key, actor, self.current.get((key, actor), self._category(key, actor)))
        if identity not in self.values:
            return False
        steps, index = self.values[identity], self.indices[identity]
        return all(step.duration == 0 and step.target == node for step in steps[index:])
