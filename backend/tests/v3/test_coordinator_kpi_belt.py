"""Carrier exposure is observable; physical cell-body integral is not inferred from leases."""

from dataclasses import replace

from app.v3.belt_models import BeltCarrier, BeltEvent
from app.v3.coordinator_metrics_belt import belt
from app.v3.light_flow_models import FlowEvent
from tests.v3.test_coordinator_kpi_fixtures import S, outcome, point, profile


def test_belt_carrier_integral_and_stopped_counter_have_explicit_units() -> None:
    value = profile()
    snapshot = point(value, 10 * S)
    carrier = BeltCarrier("O1", "P1", "P1", "complete", None, None, ())
    snapshot = replace(
        snapshot,
        belt=replace(snapshot.belt, arrived=1, completed=1, carriers=(carrier,), queue_ticks=3 * S),
    )
    events = tuple(
        FlowEvent(
            i,
            tick * S,
            "belt",
            "O1",
            belt_event=BeltEvent(
                i,
                tick * S,
                kind,
                "O1",
                "C1",
                "C1",
                None,
                None,
                None,
                (),
            ),
        )
        for i, (tick, kind) in enumerate(((3, "admitted"), (10, "completed")))
    )
    result = belt(outcome(snapshot, events), snapshot)
    assert result["admitted_carrier_ticks"] == 7 * S
    assert result["stopped_carrier_ticks"] == 3 * S
    assert result["current_admitted_carriers"] == 0
    assert result["physical_cell_occupancy_integral"]["available"] is False
    assert result["blockage_by_cause"]["available"] is False
