"""Settled resource corruption must fail even when a journal would remain balanced."""

from dataclasses import replace

import pytest

from app.v3.belt_engine import BeltEngine
from app.v3.belt_state import settled_invariants
from app.v3.conveyor_models import ConveyorSource
from tests.v3.test_belt_runtime import job, source_catalog


@pytest.fixture(scope="module")
def source() -> ConveyorSource:
    return source_catalog()


@pytest.mark.parametrize("resource", ["cell:ghost", "resource:V3_MAIN"])
def test_unknown_or_global_main_lease_is_not_an_invariant_valid_state(
    source: ConveyorSource, resource: str
) -> None:
    engine = BeltEngine(source, (job("A", ("v3:conv:PK01:main-approach",)),))
    engine.run(1_000_000, 2_000_000)
    engine.leases[resource] = "A"
    with pytest.raises(RuntimeError):
        settled_invariants(source, engine.states, engine.leases, 2_000_000)


@pytest.mark.parametrize("defect", ["missing", "owner", "duplicate_hu", "inactive", "pose"])
def test_impossible_physical_states_fail_settled_invariants(
    source: ConveyorSource, defect: str
) -> None:
    a = job("A", ("v3:conv:PK01:main-approach",))
    b = job("B", ("v3:conv:entry-arc",))
    engine = BeltEngine(source, (a, b))
    outcome = engine.run(1_000_000, 2_000_000)
    if defect == "missing":
        del engine.leases["cell:" + outcome.at_end.carriers[0].occupied_cells[0]]
    elif defect == "owner":
        engine.leases[next(iter(engine.leases))] = "absent"
    elif defect == "duplicate_hu":
        engine.states[1].job = replace(engine.states[1].job, hu_id=a.hu_id)
    elif defect == "inactive":
        engine.states[0].admitted = False
    else:
        engine.states[0].pose = None
    with pytest.raises(RuntimeError):
        settled_invariants(source, engine.states, engine.leases, 2_000_000)


def test_unreleased_hu_cannot_be_marked_completed_without_physical_admission(
    source: ConveyorSource,
) -> None:
    engine = BeltEngine(source, (job("A", ("v3:conv:entry-arc",)),))
    engine.states[0].complete = True
    with pytest.raises(RuntimeError):
        settled_invariants(source, engine.states, engine.leases, 0)
