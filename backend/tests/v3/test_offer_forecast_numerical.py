"""Actual positive synthetic HGB fitting and exact binary64 conversion controls."""

from fractions import Fraction as F
from typing import Any

import pytest
from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore[import-untyped]

from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_forecast_kernel import exact
from app.v3.offer_history import compile_offer_history
from tests.v3.test_offer_history_fixtures import choices, history_bytes


def test_positive_uniform_hgb_really_fits_validation_and_fresh_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fit_rows: list[int] = []
    actual_fit = HistGradientBoostingRegressor.fit

    def measured_fit(estimator: Any, x: Any, y: Any) -> Any:
        assert all(value == 1 for value in y)
        fit_rows.append(len(y))
        return actual_fit(estimator, x, y)

    monkeypatch.setattr(HistGradientBoostingRegressor, "fit", measured_fit)
    history = compile_offer_history(history_bytes(1, 1, rest=1), choices())
    forecast = fit_offer_forecast(history, "hgb")
    assert fit_rows == [2800, 5600]
    assert forecast.predictions == tuple((f"DEMO_{i:03d}", F(1)) for i in range(1, 201))
    assert forecast.evaluation.absolute_error == 0
    assert forecast.evaluation.actual_offers == 2800
    assert forecast.measurements.total_s > 0


def test_fraction_is_exact_binary_value_without_decimal_rounding() -> None:
    assert exact(0.1) == F(3602879701896397, 36028797018963968)
    assert exact(0.1) != F(1, 10)


@pytest.mark.parametrize("bad", [True, 1, -0.1, float("nan"), float("inf")])
def test_nonfinite_negative_or_aliased_kernel_output_rejected(bad: Any) -> None:
    with pytest.raises(ValueError):
        exact(bad)
