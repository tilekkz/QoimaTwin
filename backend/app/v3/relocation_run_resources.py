"""Replay complete base and relocation resource ownership including physical slot aliases."""

from collections import Counter
from fractions import Fraction

from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.coordinator_run_inventory import same
from app.v3.coordinator_run_resources import ResourceJournal
from app.v3.light_flow_models import FlowEvent
from app.v3.relocation_models import RelocationPlan, RelocationProfile
from app.v3.relocation_observe import RelocationEvent
from app.v3.relocation_run_inventory import RelocationInventory
from app.v3.stock_receipts import receipt_recipes


def required(plan: RelocationPlan) -> tuple[str, ...]:
    job = plan.job
    return (
        "relocation:worker:" + job.actor_id,
        "relocation:place:" + job.to_slot_id,
        "relocation:hu:" + job.hu_id,
    )


class RelocationResources(ResourceJournal):
    def __init__(
        self,
        profile: RelocationProfile,
        inventory: RelocationInventory,
        plans: tuple[RelocationPlan, ...],
        events: tuple[FlowEvent, ...],
    ) -> None:
        self.extension, self.relocations = profile, {p.job.job_id: p for p in plans}
        super().__init__(inventory, events)

    def _required(self, events: tuple[FlowEvent, ...]) -> None:
        super()._required(events)
        expected: Counter[tuple[str, int, str, bool]] = Counter()
        actual: Counter[tuple[str, int, str, bool]] = Counter()
        for event in events:
            if event.order_id not in self.relocations:
                continue
            if event.kind in {"relocation_admitted", "relocation_returned"}:
                expected.update(
                    (event.order_id, event.tick, r, event.kind == "relocation_admitted")
                    for r in required(self.relocations[event.order_id])
                )
            if event.kind in {"relocation_resource_acquired", "relocation_resource_released"}:
                if type(event) is not RelocationEvent or event.resource_id is None:
                    raise ValueError("Relocation resource has no exact name")
                actual[
                    event.order_id, event.tick, event.resource_id, event.kind.endswith("_acquired")
                ] += 1
        if actual != expected:
            raise ValueError("Relocation resource facts differ from admission/return")

    def apply(self, event: FlowEvent) -> None:
        if event.kind in {"relocation_resource_acquired", "relocation_resource_released"}:
            if not isinstance(event, RelocationEvent) or event.resource_id is None:
                raise ValueError("Relocation resource fact lost its identity")
            self._change(event.resource_id, event.order_id, event.kind.endswith("_acquired"))
        else:
            super().apply(event)

    def _change(self, resource: str, job: str, acquire: bool) -> None:
        if acquire:
            for group in (
                ("receipt:place:", "whole:place:", "relocation:place:"),
                ("receipt:worker:", "whole:worker:", "pack:worker:", "relocation:worker:"),
            ):
                suffix = next((resource[len(p) :] for p in group if resource.startswith(p)), None)
                if suffix is not None and any(p + suffix in self.leases for p in group):
                    raise ValueError("One physical slot or worker has conflicting promises")
        super()._change(resource, job, acquire)

    def check_capacity(self) -> None:
        super().check_capacity()
        places = {p.owner_id: p for p in self.extension.places}
        used: dict[str, dict[str, Fraction]] = {}
        masses = self.inventory.ledger.gross_masses()
        for container in self.inventory.ledger.snapshot().containers:
            if container.owner_id in places:
                module = places[container.owner_id].module_id
                used.setdefault(module, {})[container.container_id] = masses[container.container_id]
        for key, plan in self.relocations.items():
            if self.leases.get("relocation:place:" + plan.target.owner_id) == key:
                used.setdefault(plan.target.module_id, {})[plan.job.hu_id] = plan.gross_mass_kg
        self._receipt_promises(used)
        for place in places.values():
            members = used.get(place.module_id, {})
            if (
                len(members) > place.module_max_hus
                or sum(members.values(), Fraction(0)) > place.module_max_gross_kg
            ):
                raise ValueError("Actual module occupants and promises exceed capacity")

    def _receipt_promises(self, used: dict[str, dict[str, Fraction]]) -> None:
        places = {p.owner_id: p for p in self.extension.places}
        stock = self.inventory.profile.world.receipts.flow.stock
        tokens = {u.unit_id: u for u in stock.units}
        containers = {c.container_id: c for c in stock.containers}
        for key, offer in self.inventory.receipts.items():
            if self.leases.get("receipt:place:" + offer.slot_owner_id) != key:
                continue
            unit, wrapper = receipt_recipes(offer.definition.sku_id, tokens, containers)
            mass = offer.definition.quantity_units * unit.gross_mass_kg + wrapper.tare_kg
            used.setdefault(places[offer.slot_owner_id].module_id, {})[offer.definition.hu_id] = (
                mass
            )

    def check(self, state: CoordinatorSnapshot) -> None:
        prefixes = ("receipt:", "whole:", "pack:", "port:", "relocation:")
        actual = {key: value for key, value in state.leases if key.startswith(prefixes)}
        same(actual, self.leases, "Captured complete physical promises differ from journal")
        self.check_capacity()
