"""Extend declared replay plans and one physical actor trace with no scheduler calls."""

from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_plans import Plans
from app.v3.light_flow_models import FlowEvent
from app.v3.light_flow_state import HumanStep
from app.v3.relocation_models import RelocationPlan, RelocationProfile
from app.v3.relocation_run_inventory import RelocationInventory
from app.v3.whole_flow_plan import whole_plan


class RelocationPlans(Plans):
    def __init__(
        self,
        profile: RelocationProfile,
        inventory: RelocationInventory,
        plans: tuple[RelocationPlan, ...],
    ) -> None:
        super().__init__(profile.coordinator, inventory)
        self.relocations = {p.job.job_id: p for p in plans}
        self.places = {p.owner_id: p for p in profile.coordinator.world.places}
        self.places.update((p.target.owner_id, p.target) for p in plans)

    def _category(self, key: str, actor: str) -> str:
        return "relocation" if key in self.relocations else super()._category(key, actor)

    def _derive(self, key: str, actor: str) -> list[HumanStep]:
        if key in self.relocations:
            plan = self.relocations[key]
            if actor != plan.job.actor_id:
                raise ValueError("Relocation changed its permitted actor")
            return list(plan.steps)
        return super()._derive(key, actor)

    def _whole_or_receipt(self, key: str, actor: str) -> list[HumanStep]:
        if key not in self.inventory.whole:
            return super()._whole_or_receipt(key, actor)
        if key not in self.inventory.assignments:
            raise ValueError("Whole plan lacks actual admitted assignment")
        assigned, buffer = self.inventory.assignments[key]
        if actor != assigned:
            raise ValueError("Whole plan changed its actual actor")
        order = self.inventory.whole[key]
        contents = self.inventory.ledger.contents(order.hu_id)
        owner = contents.container.owner_id
        if owner not in self.places:
            raise ValueError("Whole plan has no actual source address")
        return whole_plan(
            self.profile.world,
            order,
            contents.container.recipe,
            self.places[owner],
            self.places[buffer],
            self.inventory.whole_ports[order.port_id],
            self.actors[actor],
        )


class RelocationMotion(MotionJournal):
    def __init__(
        self,
        profile: RelocationProfile,
        inventory: RelocationInventory,
        plans: tuple[RelocationPlan, ...],
        horizon: int,
    ) -> None:
        super().__init__(profile.coordinator, inventory, horizon)
        self.plans = RelocationPlans(profile, inventory, plans)

    def apply(self, event: FlowEvent) -> None:
        if event.kind == "relocation_admitted":
            self._assign(event)
        elif event.kind == "relocation_returned":
            self._release(event)
        else:
            super().apply(event)
