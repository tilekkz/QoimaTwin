"""Independent journal checks; expected timing comes from the hand-graph document."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_types import ManualSnapshot
from tests.v3.test_manual_acceptance_fixtures import fixture, ticks


def assert_three_hus_conserved(snapshot: ManualSnapshot) -> None:
    assert len(snapshot.owners) == 3
    assert {owner.hu_id for owner in snapshot.owners} == {"HU1", "HU2", "HU3"}
    buckets = (
        snapshot.stock_units,
        snapshot.wip_units,
        snapshot.outside_units,
        snapshot.shipped_units,
    )
    assert sum(count for bucket in buckets for sku, count in bucket if sku == "SKU") == 72
    assert all(count > 0 for bucket in buckets for _, count in bucket)


def test_whole_hus_conserve_across_horizon_and_end() -> None:
    data = fixture()
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(9), ticks(40))
    assert_three_hus_conserved(result.at_horizon)
    assert_three_hus_conserved(result.at_end)
    for snapshot in (result.at_horizon, result.at_end):
        assert len(snapshot.workers) == 24
        assert len({worker.actor_id for worker in snapshot.workers}) == 24


def test_each_finite_resource_is_held_by_at_most_one_job() -> None:
    data = fixture((1, 1))
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(20), ticks(25))
    active: dict[str, str] = {}
    for event in result.events:
        if event.kind == "lease_acquired":
            for resource in event.resource_ids:
                assert resource not in active, (event, active)
                active[resource] = event.job_id
        elif event.kind == "lease_released":
            for resource in event.resource_ids:
                assert active.pop(resource) == event.job_id
    assert active == {}
    assert result.at_end.leases == ()


def test_all_recorded_motion_uses_contiguous_real_arcs_and_pays_distance() -> None:
    data = fixture()
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(25), ticks(40))
    arcs = {arc.arc_id: arc for arc in data.arcs}
    positions = {actor.actor_id: "H" for actor in data.profile.actors}
    ends = {actor.actor_id: 0 for actor in data.profile.actors}
    motions = {
        (event.actor_id, event.motion.start_tick, event.motion.end_tick): event.motion
        for event in result.events
        if event.motion is not None
    }
    assert motions
    for (actor, start, end), motion in sorted(motions.items(), key=lambda pair: pair[0][1]):
        assert actor in ("R01", "R02")
        assert start >= ends[actor]
        assert motion.route.node_ids[0] == positions[actor]
        chain = tuple(arcs[arc_id] for arc_id in motion.route.arc_ids)
        assert tuple(arc.source for arc in chain) == motion.route.node_ids[:-1]
        assert tuple(arc.target for arc in chain) == motion.route.node_ids[1:]
        assert sum((arc.length_m for arc in chain), F(0)) == motion.route.length_m
        assert F(end - start, 1_000_000) == motion.route.length_m  # Every actor moves at1m/s.
        positions[actor], ends[actor] = motion.route.node_ids[-1], end
    assert positions["R01"] == positions["R02"] == "H"
    assert ends["R01"] == ticks(30) and ends["R02"] == ticks(15)


def test_independent_runs_are_identical_and_events_do_not_exceed_cutoff() -> None:
    first, second = fixture(), fixture()
    a = ManualEngine(first.profile, first.graph, check_invariants=True).run(ticks(25), ticks(27))
    b = ManualEngine(second.profile, second.graph, check_invariants=True).run(ticks(25), ticks(27))
    assert a == b
    assert a.at_end.tick == ticks(27)
    assert a.at_end.status == "partial"
    assert all(event.tick <= ticks(27) for event in a.events)
    assert [event.seq for event in a.events] == list(range(len(a.events)))
    worker = next(worker for worker in a.at_end.workers if worker.actor_id == "R01")
    assert worker.node_id is None
    assert worker.motion is not None and worker.motion.end_tick == ticks(30)


@pytest.mark.parametrize("kind", ["hu", "slot", "port", "actor", "missing_actor"])
def test_unknown_references_and_incomplete_rosters_fail_before_execution(kind: str) -> None:
    data = fixture((1,))
    profile = data.profile
    job = profile.jobs[0]
    if kind == "hu":
        profile = replace(profile, jobs=(replace(job, hu_id="missing"),))
    elif kind == "slot":
        profile = replace(profile, jobs=(replace(job, slot_id="missing"),))
    elif kind == "port":
        profile = replace(profile, jobs=(replace(job, port_id="missing"),))
    elif kind == "actor":
        profile = replace(
            profile, actors=(replace(profile.actors[0], actor_id="alien"), *profile.actors[1:])
        )
    else:
        profile = replace(profile, actors=profile.actors[:-1])
    with pytest.raises(ValueError):
        ManualEngine(profile, data.graph, check_invariants=True)


@pytest.mark.parametrize("heavy", [False, True])
def test_heavy_or_overweight_manual_jobs_do_not_fall_back_to_manual(heavy: bool) -> None:
    data = fixture((1,))
    hu = data.profile.handling_units[0]
    changed = (
        replace(hu, archetype="IBC", gross_mass_kg=F(654))
        if heavy
        else replace(
            hu,
            gross_mass_kg=F("15.000001"),
        )
    )
    with pytest.raises(ValueError, match="manual"):
        ManualEngine(
            replace(data.profile, handling_units=(changed,)), data.graph, check_invariants=True
        )


def test_arrival_exactly_at_horizon_is_not_silently_admitted() -> None:
    data = fixture((1,), arrival_s=4)
    with pytest.raises(ValueError):
        ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(4), ticks(20))
