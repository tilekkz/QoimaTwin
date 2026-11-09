"""Allowed exact cells must not lose offered-HU units in validation totals."""

from fractions import Fraction as F

from app.v3.offer_forecast import fit_offer_forecast, load_offer_forecast
from app.v3.offer_history import compile_offer_history
from tests.v3.test_offer_history_fixtures import choices, history_bytes


def test_validation_actual_sum_keeps_units_above_binary64_integer_range() -> None:
    history = compile_offer_history(history_bytes(2**53, 1), choices())
    forecast = fit_offer_forecast(history, "mean28")
    expected = F(14 * (2**53 + 1))
    assert forecast.evaluation.actual_offers == expected
    assert forecast.evaluation.absolute_error == 0
    assert forecast.evaluation.wape == 0
    assert forecast.predictions[:2] == (("DEMO_001", F(2**53)), ("DEMO_002", F(1)))
    restored = load_offer_forecast(forecast.frozen_bytes)
    assert restored.evaluation.actual_offers == expected
    assert restored.input_hash == forecast.input_hash
