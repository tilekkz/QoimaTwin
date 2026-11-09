"""Settled staffing state cannot lose physical role leases or teleport an active helper."""

from dataclasses import replace

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


class CorruptCoordinator(CoordinatorEngine):
    fault = "actor_lease"
    corrupted = False

    def _dispatch_round(self) -> None:
        super()._dispatch_round()
        if self.corrupted:
            return
        if self.tick == 100 * SECOND and self.fault in {"actor_lease", "motion"}:
            if self.fault == "actor_lease":
                del self.leases["staff:actor:P12"]
            else:
                operation = self.workers["P12"].operation
                assert operation is not None
                self.workers["P12"].operation = replace(operation, target_node="H12")
            self.corrupted = True
        if self.tick == 104 * SECOND and self.fault in {"station_binding", "active_node"}:
            if self.fault == "station_binding":
                del self.station_bindings["PK05"]
            else:
                self.workers["P11"].node = "H11"
            self.corrupted = True


@pytest.mark.parametrize("fault", ["actor_lease", "motion", "station_binding", "active_node"])
def test_settled_checker_rejects_forged_physical_role_state(fault: str) -> None:
    engine = CorruptCoordinator(staffing_profile(), receipt_conveyor())
    engine.fault = fault
    with pytest.raises(RuntimeError, match="ROLE"):
        engine.run(105 * SECOND, 105 * SECOND)
