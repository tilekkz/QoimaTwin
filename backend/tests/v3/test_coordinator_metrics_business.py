"""C-stage business oracles precede publication; paid return does not extend cycles."""

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_metrics import summary
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_two_orders_keep_horizon_backlog_and_business_cycle_before_paid_return() -> None:
    profile = multi_profile()
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(300 * SECOND, 400 * SECOND)
    result = summary(profile, outcome)
    horizon, end = result["at_horizon"]["unit"], result["at_end"]["unit"]
    assert (horizon["completed_units"], horizon["backlog_orders"]) == (3, 1)
    assert (end["completed_units"], end["backlog_orders"]) == (6, 0)
    assert end["cycle"] == {
        "samples": 2,
        "mean_ticks": {"numerator": 205_670_000, "denominator": 1},
        "p95_ticks": {"numerator": 219_620_000, "denominator": 1},
    }
    assert result["completion"]["business_complete_tick"] == 301_170_000
    assert result["completion"]["resource_drained_tick"] == 306_170_000
    assert result["at_end"]["tick"] == 306_170_000


def test_two_carts_at_cap_keep_two_actual_resources_and_no_completed_units() -> None:
    profile = multi_profile(candidate=False, two_carts=True)
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(84 * SECOND, 84 * SECOND)
    result = summary(profile, outcome)["at_end"]
    assert result["resources"]["cart_count"] == 2
    assert result["resources"]["busy_cart_count"] == 2
    assert result["resources"]["worker_count"] == 24
    assert result["unit"]["completed_units"] == 0
    assert result["unit"]["backlog_orders"] == 2
