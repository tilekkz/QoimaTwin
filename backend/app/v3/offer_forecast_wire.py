"""Semantic facts only: timing observations never change forecast identity."""

from dataclasses import asdict
from fractions import Fraction
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.offer_forecast_models import (
    FLOAT_POLICY,
    FORECAST_VERSION,
    TEMPORAL_POLICY,
    OfferForecast,
)


def _wire(value: Any) -> Any:
    if type(value) is Fraction:
        return [value.numerator, value.denominator]
    if type(value) in (tuple, list):
        return [_wire(child) for child in value]
    if type(value) is dict:
        return {key: _wire(child) for key, child in value.items()}
    return value


def forecast_record(value: OfferForecast) -> dict[str, Any]:
    return {
        "version": FORECAST_VERSION,
        "temporal_policy": TEMPORAL_POLICY,
        "float_policy": FLOAT_POLICY,
        "target_unit": value.history.choices.target_unit,
        "history": parse_json(value.history.frozen_bytes),
        "history_input_hash": value.history.input_hash,
        "model": value.model,
        "predictions": _wire(value.predictions),
        "training_baseline": _wire(value.training_baseline),
        "evaluation": _wire(asdict(value.evaluation)),
        "kernel_identity": value.kernel_identity,
        "operational_admission": False,
    }
