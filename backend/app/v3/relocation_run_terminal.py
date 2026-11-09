"""Relocation placement joins business completion and shared leases retain paid return drain."""

from app.v3.coordinator_run_belt import BeltJournal
from app.v3.coordinator_run_goods import GoodsJournal
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_resources import ResourceJournal
from app.v3.coordinator_run_roles import RoleJournal
from app.v3.coordinator_run_terminal import TerminalJournal
from app.v3.coordinator_run_units import UnitJournal
from app.v3.relocation_run_progress import RelocationProgress


class RelocationTerminal(TerminalJournal):
    def __init__(self, horizon: int, progress: RelocationProgress) -> None:
        super().__init__(horizon)
        self.progress = progress

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
        super().settle(tick, goods, units, motion, roles, resources, belt)
        if not all(view.placed_tick is not None for view in self.progress.views.values()):
            self.business_tick = None
            self.first_complete = None
