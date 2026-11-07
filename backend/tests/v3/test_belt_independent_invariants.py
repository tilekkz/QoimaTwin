"""Independent corruption probes for leases required before the body enters them."""

import pytest

from app.v3.belt_engine import BeltEngine
from app.v3.belt_state import settled_invariants
from tests.v3.test_belt_runtime import job, source_catalog, station_route


def test_active_chunk_requires_its_reserved_leading_cell_at_the_boundary() -> None:
    source = source_catalog()
    value = job("A", ("v3:conv:PK01:main-approach",))
    engine = BeltEngine(source, (value,), check_invariants=True)
    # .8m/.55m/s rounds upward once: the leading face only touches cell057 here.
    tick = 1_454_546
    outcome = engine.run(1_000_000, tick)
    assert outcome.at_end.carriers[0].occupied_cells == ("V3-C-MAIN-056",)
    assert engine.leases["cell:V3-C-MAIN-057"] == "A"
    del engine.leases["cell:V3-C-MAIN-057"]
    with pytest.raises(RuntimeError):
        settled_invariants(source, engine.states, engine.leases, tick)


def test_initial_station_pivot_requires_guard_before_body_enters_the_spur() -> None:
    source = source_catalog()
    engine = BeltEngine(source, (job("A", station_route(), "PK01"),), check_invariants=True)
    outcome = engine.run(200_000, 400_000)
    assert outcome.at_end.carriers[0].status == "pivot"
    assert outcome.at_end.carriers[0].motion is not None
    assert outcome.at_end.carriers[0].motion.planned_end_tick == 800_000
    guard = "resource:" + source.stations["PK01"].spur_resource_id
    assert engine.leases[guard] == "A"
    del engine.leases[guard]
    with pytest.raises(RuntimeError):
        settled_invariants(source, engine.states, engine.leases, 400_000)
