"""Completed facts and one vehicle pose; HU owner remains exclusively in StockLedger."""

from dataclasses import dataclass

from app.v3.pallet_cycle_types import ExactPose
from app.v3.pallet_shared_models import PalletSharedJob, PalletSharedJobView


@dataclass
class PalletJobState:
    spec: PalletSharedJob
    status: str = "unreleased"
    admitted_tick: int | None = None
    attached_tick: int | None = None
    released_tick: int | None = None
    completed_tick: int | None = None
    completed_steps: int = 0
    wait_reason: str | None = None

    def view(self) -> PalletSharedJobView:
        return PalletSharedJobView(
            self.spec.job_id,
            self.status,
            self.admitted_tick,
            self.attached_tick,
            self.released_tick,
            self.completed_tick,
            self.completed_steps,
            self.wait_reason,
        )


@dataclass
class PalletVehicleState:
    pose: ExactPose
    job_id: str | None = None
