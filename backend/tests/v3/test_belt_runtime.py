"""Hand-derived local and actual-source conveyor timelines, written before the DES."""

from fractions import Fraction as F
from functools import cache
from pathlib import Path

import pytest

from app.v3.belt_engine import BeltEngine
from app.v3.belt_models import BeltJob
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle


@pytest.fixture(scope="module")
def source() -> ConveyorSource:
    return source_catalog()


@cache
def source_catalog() -> ConveyorSource:
    """The reviewed source is frozen; share verification across these component tests."""
    return load_conveyor_source(source_bundle())


@cache
def source_bundle() -> V3Bundle:
    return load_v3_bundle(Path("data/v3-proposal"))


def job(identity: str, route: tuple[str, ...], station: str | None = None) -> BeltJob:
    payload = ConveyorPayload(
        identity,
        "order_tote",
        (F(".6"), F(".3"), F(".4")),
        F(1),
        "upright_xyz",
        "order-" + identity,
        "hand-fixture",
    )
    return BeltJob(
        identity, "HU-" + identity, payload, 0, route, station, 2_000_000 if station else 0
    )


def test_one_carrier_ten_metre_edge_uses_source_time_not_cell_rounding_drift(
    source: ConveyorSource,
) -> None:
    outcome = BeltEngine(source, (job("A", ("v3:conv:PK01:main-approach",)),)).run(
        10_000_000, 30_000_000
    )
    assert outcome.status == "complete"
    assert outcome.at_end.tick == 18_181_819  # ceil(10/.55 * 1e6), not sum cell ceilings
    assert outcome.at_horizon.completed == 0
    assert outcome.at_end.completed == 1
    assert outcome.at_end.queue_ticks == 0
    assert outcome.at_horizon.carriers[0].motion is not None
    assert not any(e.kind == "completed" and e.tick <= 10_000_000 for e in outcome.events)


def test_two_carriers_share_long_edge_without_locking_all_main(source: ConveyorSource) -> None:
    route = ("v3:conv:PK01:main-approach",)
    outcome = BeltEngine(source, (job("A", route), job("B", route))).run(30_000_000, 40_000_000)
    admits = {e.job_id: e.tick for e in outcome.events if e.kind == "admitted"}
    assert admits == {"A": 0, "B": 2_181_819}  # first tail clears source MAIN cell after1.2m
    assert outcome.at_end.completed == 2
    assert outcome.at_end.queue_ticks > 2_181_819
    assert any(
        e.kind == "motion_started" and e.job_id == "B" and e.tick < 18_181_819
        for e in outcome.events
    )
    assert not any("resource:V3_MAIN" in e.resources for e in outcome.events)


def station_route() -> tuple[str, ...]:
    return tuple("v3:conv:PK01:" + name for name in ("divert", "spur-in", "spur-out", "merge"))


def test_reverse_spur_keeps_owner_through_explicit_work_and_return(source: ConveyorSource) -> None:
    outcome = BeltEngine(
        source, (job("A", station_route(), "PK01"), job("B", station_route(), "PK01"))
    ).run(20_000_000, 30_000_000)
    # 2*.8 +2*ceil(.5/.55) +2*ceil(source1.7999999999999998/.55) + explicit2s.
    first_end = 11_963_638
    assert (
        next(e.tick for e in outcome.events if e.kind == "completed" and e.job_id == "A")
        == first_end
    )
    assert (
        next(e.tick for e in outcome.events if e.kind == "admitted" and e.job_id == "B")
        == first_end
    )
    reverse = [
        e for e in outcome.events if e.job_id == "A" and e.edge_id == "v3:conv:PK01:spur-out"
    ]
    assert reverse and all(e.pose is not None and e.pose.yaw_quarters == 2 for e in reverse)
    assert outcome.at_end.queue_ticks == first_end


def test_curve_is_one_shared_resource_with_four_angular_cells(source: ConveyorSource) -> None:
    route = ("v3:conv:entry-arc",)
    result = BeltEngine(source, (job("A", route), job("B", route))).run(5_000_000, 10_000_000)
    assert result.at_end.completed == 2
    assert result.at_end.tick == 7_139_984  # two serialized ceil(source arc/.55)
    assert (
        next(e.tick for e in result.events if e.kind == "admitted" and e.job_id == "B") == 3_569_992
    )
    assert any("resource:V3_CURVE_EXCLUSIVE" in e.resources for e in result.events)


def full_route(station: int = 6) -> tuple[str, ...]:
    route = ["v3:conv:feed", "v3:conv:entry-arc"]
    for index in range(6, 0, -1):
        base = f"v3:conv:PK{index:02d}:"
        route.extend((base + "main-approach", base + "east-centre"))
        if index == station:
            route.extend(base + x for x in ("divert", "spur-in", "spur-out", "merge"))
        route.append(base + "centre-west")
    return (*route, "v3:conv:main-tail")


def test_actual_source_intake_station_output_trace_and_determinism(source: ConveyorSource) -> None:
    jobs = (job("A", full_route(), "PK06"),)
    first = BeltEngine(source, jobs).run(100_000_000, 200_000_000)
    second = BeltEngine(source, jobs).run(100_000_000, 200_000_000)
    assert first == second
    assert first.at_end.tick == 149_170_000
    # Feed1454546+arc3569992+11m20000000+12halfedges10909092+5tenedges90909095
    # +tail10363637+branchhalfedges1818182+spurs6545456+pivots1600000+dwell2000000.
    assert first.at_horizon.completed == 0 and first.at_end.completed == 1
    assert {e.hu_id for e in first.events} == {"HU-A"}
    assert {e.payload_id for e in first.events} == {"A"}


def test_end_cap_retains_open_motion_without_future_completion(source: ConveyorSource) -> None:
    result = BeltEngine(source, (job("A", ("v3:conv:PK01:main-approach",)),)).run(
        1_000_000, 2_000_000
    )
    assert result.status == "partial"
    assert result.at_end.tick == 2_000_000
    assert result.at_end.carriers[0].motion is not None
    assert result.at_end.carriers[0].motion.planned_end_tick == 2_181_819
    assert result.at_end.carriers[0].pose is not None
    assert F(".08") < result.at_end.carriers[0].pose.progress < F(".12")
    assert result.at_end.completed == 0
    assert max(e.tick for e in result.events) <= 2_000_000
    assert not any(e.kind == "completed" for e in result.events)


def test_six_source_stations_share_actual_line_and_finish_without_resource_leaks(
    source: ConveyorSource,
) -> None:
    jobs = tuple(job(f"C{index}", full_route(index), f"PK{index:02d}") for index in range(1, 7))
    result = BeltEngine(source, jobs).run(200_000_000, 400_000_000)
    assert result.status == "complete"
    assert result.at_end.completed == 6
    assert result.at_end.leases == ()
    assert {carrier.hu_id for carrier in result.at_end.carriers} == {"HU-" + j.job_id for j in jobs}
    assert all(carrier.occupied_cells == () for carrier in result.at_end.carriers)
    assert [event.seq for event in result.events] == list(range(len(result.events)))


def catalog_job() -> BeltJob:
    bundle = source_bundle()
    hu = next(
        hu for hu in bundle.handling_units if hu.handling_unit_id == "v3:HU:initial:DEMO_001:01"
    )
    cargo = next(c for c in bundle.cargo_archetypes if c.archetype_id == hu.archetype_id)
    dimensions = cargo.dimensions_xyz_m
    payload = ConveyorPayload(
        "catalog-carrier",
        cargo.archetype_id,
        (F(str(dimensions[0])), F(str(dimensions[1])), F(str(dimensions[2]))),
        F(str(cargo.gross_mass_kg)),
        "upright_xyz",
        hu.handling_unit_id,
        "pinned-cargo-catalog-v3",
    )
    return BeltJob("catalog-job", hu.handling_unit_id, payload, 0, full_route(), "PK06", 2_000_000)


def test_source_catalog_small_hu_runs_without_shrinking_or_repacking(
    source: ConveyorSource,
) -> None:
    value = catalog_job()
    assert value.payload.dimensions_xyz_m == (F(".32"), F(".24"), F(".24"))
    assert value.payload.gross_mass_kg == F(".94")
    outcome = BeltEngine(source, (value,)).run(100_000_000, 200_000_000)
    assert outcome.status == "complete" and outcome.at_end.tick == 149_170_000
    assert {event.hu_id for event in outcome.events} == {"v3:HU:initial:DEMO_001:01"}
    assert {event.payload_id for event in outcome.events} == {"catalog-carrier"}
