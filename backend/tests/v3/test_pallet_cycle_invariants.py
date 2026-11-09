"""Registry conservation and complete exclusive ownership are mandatory."""

from dataclasses import replace

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_state import CycleInvariantError
from tests.v3.test_pallet_cycle_engine import engine, job
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_driver",
        "wrong_owner",
        "wrong_lease_job",
        "changed_quantity",
        "future_lease",
        "wrong_lease_resource",
    ],
)
def test_corrupt_owned_state_is_rejected(proven: LocalGeometryProof, corruption: str) -> None:
    simulation = engine(proven, (job("A"),))
    simulation.run(0, 0)
    state = simulation.state
    if corruption == "missing_driver":
        del state.leases["worker:F01"]
    elif corruption == "wrong_owner":
        state.owner = replace(state.owner, hu_id="cloned-HU")
    elif corruption == "wrong_lease_job":
        state.leases["worker:F01"] = replace(state.leases["worker:F01"], job_id="other")
    elif corruption == "changed_quantity":
        state.hu = replace(state.hu, units=25)
    elif corruption == "future_lease":
        state.leases["worker:F01"] = replace(state.leases["worker:F01"], acquired_tick=1)
    else:
        state.leases["worker:F01"] = replace(state.leases["worker:F01"], resource_id="worker:F02")
    with pytest.raises(CycleInvariantError):
        simulation.check_invariants()
