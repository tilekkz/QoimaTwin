"""Actual helper packing must retain atomic resources through the paid local transaction."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_coordinator_packing import packing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


class CorruptPacking(CoordinatorEngine):
    fault = "worker_lease"
    changed = False

    def _dispatch_round(self) -> None:
        super()._dispatch_round()
        target = 150 * SECOND if self.fault == "closed_assignment" else 146 * SECOND
        if self.changed or self.tick != target:
            return
        packing = self.packing_states["O1"]
        if self.fault == "worker_lease":
            del self.leases[packing.engine_resources[0]]
        elif self.fault == "footprint":
            del self.belt.external[sorted(packing.belt_resources)[0]]
        elif self.fault == "operation":
            self.workers[packing.actor_id].operation = None
        elif self.fault == "parcel_shape":
            packing.parcel = replace(packing.parcel, dimensions_xyz_m=(F(".12"),) * 3)
        elif self.fault == "parcel_identity":
            packing.parcel = replace(packing.parcel, payload_id="P2")
        else:
            worker = self.workers[packing.actor_id]
            worker.order_id, worker.task, worker.node = "O1", "station", "H12"
        self.changed = True


@pytest.mark.parametrize(
    "fault", ["worker_lease", "footprint", "operation", "parcel_shape", "parcel_identity"]
)
def test_mid_pack_capture_rejects_missing_actual_reservation_or_worker_operation(
    fault: str,
) -> None:
    engine = CorruptPacking(packing_profile(candidate=True), receipt_conveyor())
    engine.fault = fault
    with pytest.raises(RuntimeError, match="PACK"):
        engine.run(146 * SECOND, 146 * SECOND)


def test_closed_packing_assignment_cannot_authorize_a_forged_active_helper() -> None:
    engine = CorruptPacking(packing_profile(candidate=True), receipt_conveyor())
    engine.fault = "closed_assignment"
    with pytest.raises(RuntimeError, match=r"ROLE|PACK"):
        engine.run(150 * SECOND, 150 * SECOND)
