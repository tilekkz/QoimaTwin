"""Strict data-only N1 replay validates the complete shared physical event universe."""

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorSnapshot
from app.v3.coordinator_run_belt import BeltJournal
from app.v3.coordinator_run_boundaries import captures
from app.v3.coordinator_run_constraints import ConstraintJournal
from app.v3.coordinator_run_goods import GoodsJournal
from app.v3.coordinator_run_projection import project_outcome as project_base
from app.v3.coordinator_run_roles import RoleJournal
from app.v3.coordinator_run_units import UnitJournal
from app.v3.coordinator_run_validation import Journal, validate_outcome
from app.v3.coordinator_run_view_facts import ViewFacts
from app.v3.coordinator_validation import validate_horizon
from app.v3.light_flow_models import FlowEvent
from app.v3.relocation_models import RelocationPlan, RelocationProfile
from app.v3.relocation_native_projection import project_outcome
from app.v3.relocation_observe import RelocationOutcome, RelocationSnapshot
from app.v3.relocation_plan import plan_relocations
from app.v3.relocation_run_boundaries import event_boundaries
from app.v3.relocation_run_effects import validate_effects
from app.v3.relocation_run_inventory import RelocationInventory
from app.v3.relocation_run_motion import RelocationMotion
from app.v3.relocation_run_progress import RelocationProgress
from app.v3.relocation_run_resources import RelocationResources
from app.v3.relocation_run_terminal import RelocationTerminal


class RelocationJournal(Journal):
    inventory: RelocationInventory
    motion: RelocationMotion
    resources: RelocationResources

    def __init__(
        self,
        profile: RelocationProfile,
        source: ConveyorSource,
        outcome: RelocationOutcome,
        plans: tuple[RelocationPlan, ...],
        horizon: int,
    ) -> None:
        self.inventory = RelocationInventory(profile, plans)
        self.motion = RelocationMotion(profile, self.inventory, plans, horizon)
        self.roles = RoleJournal(profile.coordinator, self.motion)
        self.resources = RelocationResources(profile, self.inventory, plans, outcome.events)
        self.belt = BeltJournal(source, self.inventory)
        self.goods = GoodsJournal(self.inventory)
        self.units = UnitJournal(self.inventory, self.motion)
        self.progress = RelocationProgress(profile, plans, horizon)
        self.terminal = RelocationTerminal(horizon, self.progress)
        self.constraints = ConstraintJournal(profile.coordinator)
        self.view_facts = ViewFacts(self.inventory, outcome.events)

    def apply(self, event: FlowEvent) -> None:
        self.progress.before(event, self)
        super().apply(event)

    def settle(self, tick: int) -> None:
        self.progress.settle(tick, self)
        super().settle(tick)

    def check(self, state: CoordinatorSnapshot) -> None:
        if type(state) is not RelocationSnapshot:
            raise ValueError("Nonempty N1 run requires exact extension captures")
        super().check(state)
        self.progress.check(state)


def validate_relocation_outcome(
    profile: RelocationProfile,
    conveyor: ConveyorSource,
    outcome: CoordinatorOutcome,
    horizon_tick: int,
    end_tick: int,
) -> None:
    plans = plan_relocations(profile)
    validate_horizon(profile.coordinator, horizon_tick, end_tick)
    if any(p.job.arrival_tick >= horizon_tick for p in plans):
        raise ValueError("Relocation arrival must precede the admission horizon")
    if not plans:
        if type(outcome) is not CoordinatorOutcome:
            raise ValueError("Empty N1 extension requires exact original coordinator outcome")
        project_base(profile.coordinator, outcome)
        validate_outcome(profile.coordinator, conveyor, outcome, horizon_tick, end_tick)
        return
    if type(outcome) is not RelocationOutcome:
        raise ValueError("Nonempty N1 run requires exact relocation outcome")
    project_outcome(profile.coordinator, outcome)
    event_boundaries(profile, outcome)
    points = captures(outcome, horizon_tick, end_tick)
    if outcome.status == "partial" and outcome.at_end.tick != end_tick:
        raise ValueError("Partial N1 outcome lost its requested observation cap")
    validate_effects(profile, outcome.events, horizon_tick, outcome.at_end.tick)
    journal = RelocationJournal(profile, conveyor, outcome, plans, horizon_tick)
    _replay(journal, outcome, points)
    journal.terminal.check(outcome, journal.roles)
    journal.constraints.check(outcome, journal.roles)


def _replay(
    journal: RelocationJournal, outcome: RelocationOutcome, points: tuple[CoordinatorSnapshot, ...]
) -> None:
    cursor = 0
    ticks = sorted({0, *(e.tick for e in outcome.events), *(s.tick for s in points)})
    grouped: dict[int, list[CoordinatorSnapshot]] = {}
    for point in points:
        grouped.setdefault(point.tick, []).append(point)
    for tick in ticks:
        while cursor < len(outcome.events) and outcome.events[cursor].tick == tick:
            journal.apply(outcome.events[cursor])
            cursor += 1
        journal.settle(tick)
        for point in grouped.get(tick, ()):
            journal.check(point)
