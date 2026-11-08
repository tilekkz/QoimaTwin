"""Business completion, physical drain and observation end are independent evidence."""

from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_run_belt import BeltJournal
from app.v3.coordinator_run_goods import GoodsJournal
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_resources import ResourceJournal
from app.v3.coordinator_run_roles import RoleJournal
from app.v3.coordinator_run_units import UnitJournal


class TerminalJournal:
    def __init__(self, horizon: int) -> None:
        self.horizon = horizon
        self.business_tick: int | None = None
        self.resource_tick: int | None = 0
        self.was_idle = True
        self.first_complete: int | None = None

    def settle(
        self,
        tick: int,
        goods: GoodsJournal,
        units: UnitJournal,
        motion: MotionJournal,
        roles: RoleJournal,
        resources: ResourceJournal,
        belt: BeltJournal,
    ) -> None:
        business = (
            all(s.shipped_tick is not None for s in units.orders.values())
            and all(s.shipped_tick is not None for s in goods.whole.values())
            and all(
                s.placed_tick is not None or s.offer.arrival_tick >= self.horizon
                for s in goods.receipts.values()
            )
        )
        if business and self.business_tick is None:
            self.business_tick = tick
        idle = (
            not resources.leases
            and not roles.leases()
            and not motion.cart_orders
            and not belt.leases
            and not belt.external
            and all(
                w.order_id is None and w.operation is None and w.waiting_since is None
                for w in motion.workers.values()
            )
            and all(s.complete for s in belt.states.values())
        )
        if idle and not self.was_idle:
            self.resource_tick = tick
        elif not idle:
            self.resource_tick = None
        self.was_idle = idle
        done = (
            business
            and idle
            and all(r.status in {"restored", "rejected"} for r in roles.views.values())
        )
        if done and tick >= self.horizon and self.first_complete is None:
            self.first_complete = tick

    def check(self, outcome: CoordinatorOutcome, roles: RoleJournal) -> None:
        if outcome.business_complete_tick != self.business_tick:
            raise ValueError("Business completion differs from actual goods handovers")
        if outcome.resource_drained_tick != self.resource_tick:
            raise ValueError("Resource drain differs from actual paid return and release")
        complete = self.first_complete is not None
        if outcome.status != ("complete" if complete else "partial"):
            raise ValueError("Operational status differs from actual goods/resources/roles")
        if complete and outcome.at_end.tick != self.first_complete:
            raise ValueError(
                "Complete outcome extends beyond its actual first terminal observation"
            )
        staffing = (
            "violated"
            if outcome.constraint_violations
            else (
                "valid"
                if all(v.status in {"restored", "rejected"} for v in roles.views.values())
                else "partial"
            )
        )
        if outcome.staffing_status != staffing:
            raise ValueError("Staffing status differs from actual role/constraint evidence")
