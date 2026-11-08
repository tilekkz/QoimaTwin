"""Conservative whole-port reservation includes approach; physical service is only35 seconds."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_metrics_ports import ports
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_whole_reservation_and_actual_service_use_separate_observed_integrals() -> None:
    profile = replace(staffing_profile(whole_order=True), intents=())
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(46 * SECOND, 52 * SECOND)
    horizon = ports(profile, outcome, outcome.at_horizon)
    end = ports(profile, outcome, outcome.at_end)
    first = next(r for r in horizon if r["cargo_class"] == "STANDARD_CARTON")
    last = next(r for r in end if r["cargo_class"] == "STANDARD_CARTON")
    assert (first["reservation_ticks"], first["service_ticks"]) == (39 * SECOND, 34 * SECOND)
    assert first["service_fraction"] == {"numerator": 17, "denominator": 23}
    assert (last["reservation_ticks"], last["service_ticks"]) == (40 * SECOND, 35 * SECOND)
    assert (last["completed_jobs"], last["completed_units"]) == (1, 24)
