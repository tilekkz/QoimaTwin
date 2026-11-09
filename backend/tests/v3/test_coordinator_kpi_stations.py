"""Bench ownership ends at clear, while the assigned worker can still return home."""

from dataclasses import replace

import pytest

from app.v3.coordinator_metrics_stations import stations
from app.v3.coordinator_packing_models import PackingView
from app.v3.light_flow_models import FlowEvent, FlowOperation
from tests.v3.test_coordinator_kpi_fixtures import S, outcome, point, profile


@pytest.mark.parametrize(
    ("t", "pack", "clear", "bench", "cleared"),
    [
        (15, 3, 0, 5, 0),
        (16, 3, 1, 6, 1),
        (20, 3, 1, 6, 1),
    ],
)
def test_station_service_and_reservation_have_distinct_release_boundaries(
    t: int,
    pack: int,
    clear: int,
    bench: int,
    cleared: int,
) -> None:
    value = profile()
    view = PackingView(
        "O1",
        "K06",
        "PK06",
        None,
        "returning",
        10 * S,
        15 * S,
        16 * S if t >= 16 else None,
        20 * S if t >= 20 else None,
        (),
    )
    snapshot = replace(point(value, t * S), packing=(view,))
    events = tuple(
        FlowEvent(
            i,
            a * S,
            "operation_started",
            "O1",
            "K06",
            FlowOperation(kind, "O1", a * S, b * S, "PACK", "PACK", None),
        )
        for i, (kind, a, b) in enumerate((("pack", 12, 15), ("clear", 15, 16)))
    )
    rows = stations(value, outcome(snapshot, events), snapshot)
    row = next(row for row in rows if row["station_id"] == "PK06")
    assert (row["pack_service_ticks"], row["clear_service_ticks"], row["bench_reserved_ticks"]) == (
        pack * S,
        clear * S,
        bench * S,
    )
    assert row["cleared_orders"] == cleared
    assert len(rows) == 6
    assert all(row["bench_reserved_ticks"] == 0 for row in rows if row["station_id"] != "PK06")


def test_zero_window_station_utilization_is_undefined() -> None:
    value = profile()
    snapshot = point(value, 0)
    assert all(
        row["service_fraction"] is None for row in stations(value, outcome(snapshot), snapshot)
    )


def test_duplicate_pack_operation_cannot_fit_silently_inside_long_bench_reservation() -> None:
    value = profile()
    view = PackingView("O1", "K06", "PK06", None, "returning", 0, 8 * S, 9 * S, None, ())
    snapshot = replace(point(value, 10 * S), packing=(view,))
    op = FlowOperation("pack", "O1", 5 * S, 8 * S, "PACK", "PACK", None)
    events = tuple(FlowEvent(i, 5 * S, "operation_started", "O1", "K06", op) for i in (0, 1))
    with pytest.raises(ValueError, match="overlap"):
        stations(value, outcome(snapshot, events), snapshot)
