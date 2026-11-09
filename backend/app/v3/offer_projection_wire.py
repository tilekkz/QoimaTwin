"""Closed projection records bind forecast semantics while excluding CPU observations."""

from typing import Any, cast

from app.v3.coordinator_native_decode import decode
from app.v3.flow_profile_wire import record
from app.v3.offer_projection_models import (
    SCOPE,
    VERSION,
    OfferProjectionChoices,
    OfferProjectionInputs,
)
from app.v3.workload_wire import source_dict


def choices_from_wire(value: object) -> OfferProjectionChoices:
    return cast(OfferProjectionChoices, decode(OfferProjectionChoices, value))


def projection_record(value: OfferProjectionInputs) -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "scope": SCOPE,
        "forecast_bytes": value.forecast_bytes.decode("utf-8"),
        "forecast_id": value.forecast_id,
        "source": source_dict(value.source),
        "initial_hus": record(value.initial_hus),
        "choices": record(value.choices),
        "offers": record(value.offers),
        "operational_admission": False,
        "actual_test_stream": False,
        "throughput_claim": False,
    }
