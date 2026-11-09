"""Literal constant and zero oracles; no source-runtime or throughput claims."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any, cast

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.offer_forecast import fit_offer_forecast, load_offer_forecast, verify_offer_forecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_history_models import OfferHistoryInputs
from tests.v3.test_offer_history_fixtures import choices, history, history_bytes

__all__ = ["history"]


def test_mean28_constants_and_roundtrip(history: OfferHistoryInputs) -> None:
    forecast = fit_offer_forecast(history, "mean28")
    assert forecast.predictions[:2] == (("DEMO_001", F(1)), ("DEMO_002", F(3)))
    assert all(value == 0 for _, value in forecast.predictions[2:])
    assert forecast.training_baseline == forecast.predictions
    assert forecast.evaluation.absolute_error == 0 and forecast.evaluation.wape == 0
    assert forecast.evaluation.validation_rows == 2800
    assert forecast.evaluation.validation_fit_rows == 2800
    assert forecast.evaluation.final_fit_rows == 5600
    fresh = verify_offer_forecast(forecast)
    assert fresh == load_offer_forecast(forecast.frozen_bytes) == forecast
    assert fresh.source is not forecast.source
    assert b"cpu" not in forecast.frozen_bytes


@pytest.mark.parametrize("model", ["mean28", "hgb"])
def test_all_zero_boundary(model: str) -> None:
    source = compile_offer_history(history_bytes(0, 0), choices())
    forecast = fit_offer_forecast(source, model)
    assert all(value == 0 for _, value in forecast.predictions)
    assert forecast.evaluation.wape is None
    assert forecast.evaluation.actual_offers == 0


def test_rehashed_prediction_cannot_claim_kernel_result(history: OfferHistoryInputs) -> None:
    forecast = fit_offer_forecast(history, "mean28")
    value = parse_json(forecast.frozen_bytes)
    value["predictions"][0][1] = [999, 1]
    with pytest.raises(ValueError):
        load_offer_forecast(canonical_bytes(value))
    with pytest.raises(ValueError):
        verify_offer_forecast(
            replace(
                forecast, predictions=(("DEMO_001", cast(Any, True)), *forecast.predictions[1:])
            )
        )
