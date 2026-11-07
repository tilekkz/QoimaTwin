"""Observation exposure and strict explicit-input boundaries."""

from dataclasses import replace

import pytest

from app.v3.belt_engine import BeltEngine
from app.v3.conveyor_models import ConveyorSource
from tests.v3.test_belt_runtime import job, source_catalog, station_route


@pytest.fixture(scope="module")
def source() -> ConveyorSource:
    return source_catalog()


def test_queue_integral_clips_at_h_and_end_without_prearrival_exposure(
    source: ConveyorSource,
) -> None:
    first = job("A", ("v3:conv:entry-arc",))
    second = replace(job("B", first.route), arrival_tick=500_000)
    outcome = BeltEngine(source, (first, second)).run(1_000_000, 3_000_000)
    assert outcome.at_horizon.queue_ticks == 500_000
    assert outcome.at_end.queue_ticks == 2_500_000
    assert outcome.at_horizon.arrived == 2 and outcome.at_end.completed == 0


def test_horizon_includes_handoff_exactly_and_excludes_future_completions(
    source: ConveyorSource,
) -> None:
    jobs = (job("A", ("v3:conv:PK01:main-approach",)),)
    before = BeltEngine(source, jobs).run(18_181_818, 30_000_000)
    exact = BeltEngine(source, jobs).run(18_181_819, 30_000_000)
    assert before.at_horizon.completed == 0 and exact.at_horizon.completed == 1
    assert before.at_end.tick == exact.at_end.tick == 18_181_819
    assert exact.at_horizon.leases == ()


def test_empty_run_completes_at_zero_and_engine_is_single_use(source: ConveyorSource) -> None:
    engine = BeltEngine(source, ())
    result = engine.run(10, 20)
    assert result.at_end.tick == 0 and result.at_horizon.tick == 10
    assert result.at_horizon.queue_ticks == 0 and result.events == ()
    with pytest.raises(ValueError):
        engine.run(10, 20)


@pytest.mark.parametrize("kind", ["unknown", "disconnected", "station", "missing_dwell", "heavy"])
def test_unsupported_or_incomplete_route_never_gets_a_fallback(
    source: ConveyorSource, kind: str
) -> None:
    value = job("A", ("v3:conv:PK01:main-approach",))
    if kind == "unknown":
        value = replace(value, route=("upstream-teleport",))
    elif kind == "disconnected":
        value = replace(value, route=("v3:conv:PK01:centre-west", "v3:conv:PK06:east-centre"))
    elif kind == "station":
        value = replace(value, station_id="PK06")
    elif kind == "missing_dwell":
        value = replace(value, route=station_route())
    else:
        value = replace(value, payload=replace(value.payload, kind="HEAVY_BOX"))
    with pytest.raises(ValueError):
        BeltEngine(source, (value,))


def test_duplicate_physical_hu_and_out_of_horizon_arrival_reject(source: ConveyorSource) -> None:
    first, second = job("A", ("v3:conv:entry-arc",)), job("B", ("v3:conv:entry-arc",))
    with pytest.raises(ValueError):
        BeltEngine(source, (first, replace(second, hu_id=first.hu_id)))
    with pytest.raises(ValueError):
        BeltEngine(source, (replace(first, arrival_tick=10),)).run(10, 20)
