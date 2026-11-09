"""Claude review: statically impossible explicit jobs must fail closed (ADR 0031).

`validate_profile` documents "Fail closed on incomplete manual-execution profiles, before
creating events". The source compiler already rejects these shapes; a directly supplied
ExecutionProfile must not turn them into an endless honest-looking "waiting" run instead.
No timing oracle is used: the expected outcome is a construction-time ValueError.
"""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_types import HandlingUnit, InitialPlacement, PortSpec, TimedJob
from tests.v3.test_execution_manual import fixture, tick


def test_outbound_from_a_slot_the_hu_never_occupies_is_rejected() -> None:
    profile, graph = fixture("outbound")
    other = replace(profile.slots[0], place_id="slot2")
    job = TimedJob("job1", 0, "outbound", "HU1", "port", "slot2")
    bad = replace(profile, slots=(*profile.slots, other), jobs=(job,))
    with pytest.raises(ValueError, match="origin"):
        ManualEngine(bad, graph, check_invariants=True)


@pytest.mark.parametrize("change", ["no_skill", "too_heavy"])
def test_job_without_any_capable_eligible_worker_is_rejected(change: str) -> None:
    profile, graph = fixture("inbound")
    if change == "no_skill":
        actors = tuple(replace(a, skills=frozenset()) for a in profile.actors)
    else:
        actors = tuple(replace(a, max_gross_mass_kg=F(1, 2)) for a in profile.actors)
    with pytest.raises(ValueError, match="capable"):
        ManualEngine(replace(profile, actors=actors), graph, check_invariants=True)


def test_receipt_into_a_slot_whose_occupant_never_leaves_is_rejected() -> None:
    profile, graph = fixture("inbound")
    blocker = HandlingUnit("HU2", "SKU2", 5, "SMALL_CARTON", F(1), (F(".2"),) * 3)
    bad = replace(
        profile,
        handling_units=(*profile.handling_units, blocker),
        initial_placements=(InitialPlacement("HU2", "slot"),),
    )
    with pytest.raises(ValueError, match="occupied"):
        ManualEngine(bad, graph, check_invariants=True)


def test_received_hu_may_later_ship_from_its_receipt_slot() -> None:
    # ADR 0031: "the same received HU may have a later outbound job". Must stay accepted.
    profile, graph = fixture("inbound")
    actors = tuple(
        replace(a, skills=frozenset({"receive", "ship"})) if a.actor_id == "R01" else a
        for a in profile.actors
    )
    out_buffer = replace(profile.ports[0].buffer_places[0], place_id="out_buffer")
    out_port = PortSpec(
        "out", "outbound", "P", (out_buffer,), (("SMALL_CARTON", tick(10)),),
        ((0, tick(1000)),), frozenset({"R01"}),
    )  # fmt: skip
    ship = TimedJob("job2", 0, "outbound", "HU1", "out", "slot")
    ok = replace(
        profile, actors=actors, ports=(*profile.ports, out_port), jobs=(*profile.jobs, ship)
    )
    result = ManualEngine(ok, graph, check_invariants=True).run(tick(500), tick(900))
    assert result.at_end.status == "complete"
    assert result.at_end.shipped_units == (("SKU1", 24),)
    assert result.at_end.stock_units == result.at_end.outside_units == ()
