"""Strict C event/capture authority; replay is data-only and does not execute a scheduler."""

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_run_belt import BeltJournal
from app.v3.coordinator_run_boundaries import captures, event_boundaries
from app.v3.coordinator_run_constraints import ConstraintJournal
from app.v3.coordinator_run_effects import validate_effects
from app.v3.coordinator_run_goods import GoodsJournal
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_resources import ResourceJournal
from app.v3.coordinator_run_roles import RoleJournal
from app.v3.coordinator_run_terminal import TerminalJournal
from app.v3.coordinator_run_units import UnitJournal
from app.v3.coordinator_run_view_facts import ViewFacts
from app.v3.light_flow_models import FlowEvent


class Journal:
    def __init__(
        self,
        profile: CoordinatorProfile,
        source: ConveyorSource,
        outcome: CoordinatorOutcome,
        horizon: int,
    ) -> None:
        self.inventory = InventoryJournal(profile)
        self.motion = MotionJournal(profile, self.inventory, horizon)
        self.roles = RoleJournal(profile, self.motion)
        self.resources = ResourceJournal(self.inventory, outcome.events)
        self.belt = BeltJournal(source, self.inventory)
        self.goods = GoodsJournal(self.inventory)
        self.units = UnitJournal(self.inventory, self.motion)
        self.terminal = TerminalJournal(horizon)
        self.constraints = ConstraintJournal(profile)
        self.view_facts = ViewFacts(self.inventory, outcome.events)

    def apply(self, event: FlowEvent) -> None:
        self.roles.before(event, self.resources.leases)
        self.constraints.apply(event, self.motion, self.inventory, self.resources)
        self.motion.apply(event)
        self.roles.apply(event)
        self.inventory.apply(event)
        self.resources.apply(event)
        self.goods.apply(event)
        self.units.apply(event)
        self.belt.apply(event)
        self.resources.check_capacity()
        self.view_facts.apply(event)

    def settle(self, tick: int) -> None:
        self.terminal.settle(
            tick, self.goods, self.units, self.motion, self.roles, self.resources, self.belt
        )

    def check(self, state: CoordinatorSnapshot) -> None:
        for journal in (
            self.inventory,
            self.motion,
            self.roles,
            self.resources,
            self.goods,
            self.units,
            self.belt,
        ):
            journal.check(state)
        expected = {**self.resources.leases, **self.roles.leases()}
        prefix = "cart:" if self.inventory.profile.unit_resources is not None else ""
        for cart, key in self.motion.cart_orders.items():
            expected[prefix + cart if prefix else "cart"] = key
        combined = tuple(sorted(expected.items())) + tuple(sorted(self.belt.external.items()))
        same(
            state.leases, combined, "Captured complete resource universe differs from actual leases"
        )


def validate_outcome(
    profile: CoordinatorProfile,
    source: ConveyorSource,
    outcome: CoordinatorOutcome,
    horizon: int,
    cap: int,
) -> None:
    event_boundaries(profile, outcome)
    points = captures(outcome, horizon, cap)
    validate_effects(profile, outcome.events, horizon, outcome.at_end.tick)
    journal = Journal(profile, source, outcome, horizon)
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
    journal.terminal.check(outcome, journal.roles)
    journal.constraints.check(outcome, journal.roles)
