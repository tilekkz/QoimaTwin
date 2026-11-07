"""Hand geometry/timing oracles across cell, curve and stopped-pivot boundaries."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.belt_engine import BeltEngine
from tests.v3.test_belt_runtime import job, source_catalog, station_route


def ceil_microseconds(seconds: F) -> int:
    scaled = seconds * 1_000_000
    return -(-scaled.numerator // scaled.denominator)


def test_leading_touch_and_positive_overlap_are_distinct_settled_observations() -> None:
    source = source_catalog()
    value = job("A", ("v3:conv:PK01:main-approach",))
    front_tick = ceil_microseconds(F(".8") / F(".55"))
    outcome = BeltEngine(source, (value,), check_invariants=True).run(front_tick, front_tick + 1)
    before, after = outcome.at_horizon.carriers[0], outcome.at_end.carriers[0]
    assert before.occupied_cells == ("V3-C-MAIN-056",)
    assert after.occupied_cells == ("V3-C-MAIN-056", "V3-C-MAIN-057")
    assert before.pose is not None and before.pose.progress == F(".08")
    assert after.pose is not None and F(".08") < after.pose.progress < F(".12")
    assert after.motion is not None
    assert after.motion.planned_end_tick == ceil_microseconds(F("1.2") / F(".55"))
    assert outcome.status == "partial" and outcome.at_end.completed == 0
    assert all(event.tick <= front_tick + 1 for event in outcome.events)


def test_tail_release_admits_following_body_at_the_same_tick_without_overlap() -> None:
    source = source_catalog()
    route = ("v3:conv:PK01:main-approach",)
    tick = ceil_microseconds(F("1.2") / F(".55"))
    outcome = BeltEngine(source, (job("A", route), job("B", route)), check_invariants=True).run(
        tick, tick + 1
    )
    first, second = outcome.at_horizon.carriers
    assert first.occupied_cells == ("V3-C-MAIN-057",)
    assert second.occupied_cells == ("V3-C-MAIN-055", "V3-C-MAIN-056")
    assert first.status == second.status == "motion"
    assert outcome.at_horizon.queue_ticks == tick
    assert outcome.at_horizon.arrived == 2 and outcome.at_horizon.completed == 0
    release = next(e for e in outcome.events if e.tick == tick and e.kind == "leases_released")
    acquire = next(e for e in outcome.events if e.tick == tick and e.kind == "leases_acquired")
    assert release.job_id == "A" and acquire.job_id == "B" and release.seq < acquire.seq
    assert not any("resource:V3_MAIN" in event.resources for event in outcome.events)


@pytest.mark.parametrize("depth", [F(".24"), F(".4")])
def test_cell_subdivision_preserves_one_ceiling_for_the_whole_edge(depth: F) -> None:
    source = source_catalog()
    value = job("A", ("v3:conv:PK01:main-approach",))
    value = replace(
        value, payload=replace(value.payload, dimensions_xyz_m=(F(".6"), F(".3"), depth))
    )
    finish = ceil_microseconds(F(10) / F(".55"))
    outcome = BeltEngine(source, (value,), check_invariants=True).run(finish, finish + 1)
    assert outcome.at_horizon.completed == 1 and outcome.at_end.tick == finish
    assert outcome.at_end.leases == () and outcome.at_end.queue_ticks == 0
    motions = [event for event in outcome.events if event.kind == "motion_started"]
    assert all(event.planned_end_tick is not None for event in motions)
    assert sum((event.planned_end_tick or 0) - event.tick for event in motions) == finish


def test_curve_owner_hands_off_only_after_whole_arc_completion() -> None:
    source = source_catalog()
    route = ("v3:conv:entry-arc",)
    finish = ceil_microseconds(F("1.9634954084936207") / F(".55"))
    outcome = BeltEngine(source, (job("A", route), job("B", route)), check_invariants=True).run(
        finish, finish + 1
    )
    first, second = outcome.at_horizon.carriers
    assert first.status == "complete" and first.occupied_cells == ()
    assert second.status == "motion"
    assert second.occupied_cells == ("V3-C-ARC-00", "V3-C-FEED")
    assert dict(outcome.at_horizon.leases)["resource:V3_CURVE_EXCLUSIVE"] == "B"
    assert outcome.at_horizon.queue_ticks == finish
    releases = [e.seq for e in outcome.events if e.tick == finish and e.kind == "leases_released"]
    acquires = [e.seq for e in outcome.events if e.tick == finish and e.kind == "leases_acquired"]
    assert releases and acquires and max(releases) < min(acquires)


def test_divert_pivots_before_motion_and_partial_yaw_does_not_move_the_body() -> None:
    source = source_catalog()
    value = job("A", station_route(), "PK01")
    outcome = BeltEngine(source, (value,), check_invariants=True).run(400_000, 800_000)
    turning, moving = outcome.at_horizon.carriers[0], outcome.at_end.carriers[0]
    assert turning.status == "pivot" and turning.pose is not None
    assert turning.pose.progress == 0 and turning.pose.yaw_quarters == F(3, 2)
    assert moving.status == "motion" and moving.pose is not None
    assert moving.pose.progress == 0 and moving.pose.yaw_quarters == 2
    assert turning.occupied_cells == moving.occupied_cells
    assert outcome.status == "partial"


def test_reverse_spur_and_merge_pivot_keep_physical_yaw_until_turning() -> None:
    source = source_catalog()
    half = ceil_microseconds(F(".5") / F(".55"))
    spur = ceil_microseconds(F("1.7999999999999998") / F(".55"))
    merge_end = 800_000 + 2 * half + 2 * spur + 2_000_000
    outcome = BeltEngine(source, (job("A", station_route(), "PK01"),), check_invariants=True).run(
        merge_end, merge_end + 400_000
    )
    start, middle = outcome.at_horizon.carriers[0], outcome.at_end.carriers[0]
    assert start.status == middle.status == "pivot"
    assert start.pose is not None and middle.pose is not None
    assert start.pose.progress == middle.pose.progress == 1
    assert start.pose.yaw_quarters == 2 and middle.pose.yaw_quarters == F(3, 2)
    backwards = [e for e in outcome.events if e.edge_id == "v3:conv:PK01:spur-out"]
    assert backwards and all(e.pose is not None and e.pose.yaw_quarters == 2 for e in backwards)
    guard = "resource:" + source.stations["PK01"].spur_resource_id
    assert dict(outcome.at_end.leases)[guard] == "A"
    assert outcome.at_end.completed == 0


def test_component_handoff_before_horizon_preserves_separate_observation_ticks() -> None:
    source = source_catalog()
    value = job("A", ("v3:conv:PK01:east-centre",))
    finish = ceil_microseconds(F(".5") / F(".55"))
    outcome = BeltEngine(source, (value,), check_invariants=True).run(2_000_000, 3_000_000)
    assert outcome.status == "complete" and outcome.at_end.tick == finish
    assert outcome.at_horizon.tick == 2_000_000
    assert outcome.at_horizon.completed == outcome.at_end.completed == 1
    assert outcome.at_horizon.leases == outcome.at_end.leases == ()
    assert max(event.tick for event in outcome.events) == finish
