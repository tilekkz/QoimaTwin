"""Freshly reconstruct source, history and model output before accepting any forecast."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.offer_forecast_kernel import calculate, identity, validate_cpu
from app.v3.offer_forecast_models import OfferForecast
from app.v3.offer_forecast_wire import forecast_record
from app.v3.offer_history import load_offer_history, verify_offer_history
from app.v3.offer_history_models import OfferHistoryInputs
from app.v3.workload_policy import fields
from app.v3.workload_validation import name


def _fit(history: OfferHistoryInputs, model: str) -> OfferForecast:
    predictions, baseline, evaluation, cpu = calculate(history, model)
    value = OfferForecast(
        history.source, history, model, predictions, baseline, evaluation, identity(), b"", "", cpu
    )
    raw = canonical_bytes(forecast_record(value))
    return replace(value, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def fit_offer_forecast(history: OfferHistoryInputs, model: str) -> OfferForecast:
    return _fit(verify_offer_history(history), model)


def load_offer_forecast(raw: bytes) -> OfferForecast:
    if type(raw) is not bytes:
        raise ValueError("Exact immutable forecast envelope required")
    value = fields(
        parse_json(raw),
        {
            "version",
            "temporal_policy",
            "float_policy",
            "target_unit",
            "history",
            "history_input_hash",
            "model",
            "predictions",
            "training_baseline",
            "evaluation",
            "kernel_identity",
            "operational_admission",
        },
    )
    history = load_offer_history(canonical_bytes(value["history"]))
    expected = _fit(history, name(value["model"]))
    if expected.frozen_bytes != raw:
        raise ValueError("Forecast differs from exact fresh numerical and source authority")
    return expected


def verify_offer_forecast(value: OfferForecast) -> OfferForecast:
    if type(value) is not OfferForecast:
        raise ValueError("Exact OfferForecast required")
    validate_cpu(value.measurements)
    expected = load_offer_forecast(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
