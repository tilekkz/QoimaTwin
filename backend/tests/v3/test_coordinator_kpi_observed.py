"""Additive reducer composition; this is not a substitute for native engine acceptance."""

from app.v3.coordinator_metrics_observed import OBSERVED_KPI_VERSION, observed_kpis
from tests.v3.test_coordinator_kpi_fixtures import outcome, point, profile


def test_idle_zero_window_keeps_all_resources_and_unknown_metrics_explicit() -> None:
    value = profile()
    snapshot = point(value, 0)
    result = observed_kpis(value, outcome(snapshot), snapshot)
    assert result["version"] == OBSERVED_KPI_VERSION
    assert len(result["travel"]["actors"]) == 24
    assert len(result["stations"]) == 6
    assert result["travel"]["total_paid_distance_m"] == {"numerator": 0, "denominator": 1}
    assert result["belt"]["mean_admitted_carriers"] is None
    assert result["belt"]["blockage_by_cause"]["value"] is None
    assert result["inventory"]["onsite_units"] == 24
    assert all(row["mean_containers"] is None for row in result["materials"])
