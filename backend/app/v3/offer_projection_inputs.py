"""Authenticate a forecast and freeze predicted planning offers without a future test stream."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.offer_forecast import load_offer_forecast, verify_offer_forecast
from app.v3.offer_forecast_models import OfferForecast
from app.v3.offer_projection_materialize import materialize_projection
from app.v3.offer_projection_models import (
    SCOPE,
    VERSION,
    OfferProjectionChoices,
    OfferProjectionInputs,
)
from app.v3.offer_projection_source import fresh_projection_source
from app.v3.offer_projection_validation import validate_choices
from app.v3.offer_projection_wire import choices_from_wire, projection_record
from app.v3.workload_policy import fields
from app.v3.workload_validation import name


def _compose(forecast: OfferForecast, choices: OfferProjectionChoices) -> OfferProjectionInputs:
    source, stock, ports = fresh_projection_source(forecast.source)
    offers = materialize_projection(
        source, forecast.predictions, choices, ports, forecast.input_hash
    )
    choices = replace(
        choices, port_mix=tuple(sorted(choices.port_mix, key=lambda r: (r.sku_id, r.port_id)))
    )
    value = OfferProjectionInputs(
        forecast.frozen_bytes, forecast.input_hash, source, stock, choices, offers, b"", ""
    )
    raw = canonical_bytes(projection_record(value))
    return replace(value, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def compile_offer_projection(
    forecast: OfferForecast,
    choices: OfferProjectionChoices,
) -> OfferProjectionInputs:
    validate_choices(choices)
    return _compose(verify_offer_forecast(forecast), choices)


def load_offer_projection(raw: bytes) -> OfferProjectionInputs:
    if type(raw) is not bytes:
        raise ValueError("EXACT_OFFER_PROJECTION_BYTES_REQUIRED")
    value = fields(
        parse_json(raw),
        {
            "schema_version",
            "scope",
            "forecast_bytes",
            "forecast_id",
            "source",
            "initial_hus",
            "choices",
            "offers",
            "operational_admission",
            "actual_test_stream",
            "throughput_claim",
        },
    )
    if canonical_bytes(value) != raw:
        raise ValueError("CANONICAL_OFFER_PROJECTION_BYTES_REQUIRED")
    if value["schema_version"] != VERSION or value["scope"] != SCOPE:
        raise ValueError("UNSUPPORTED_OFFER_PROJECTION_VERSION")
    forecast = load_offer_forecast(name(value["forecast_bytes"]).encode("utf-8"))
    result = _compose(forecast, choices_from_wire(value["choices"]))
    if result.frozen_bytes != raw:
        raise ValueError("FORECAST_SOURCE_OR_PREDICTED_PROJECTION_CHANGED")
    return result


def verify_offer_projection(value: OfferProjectionInputs) -> OfferProjectionInputs:
    if type(value) is not OfferProjectionInputs:
        raise ValueError("EXACT_OFFER_PROJECTION_INPUTS_REQUIRED")
    expected = load_offer_projection(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
