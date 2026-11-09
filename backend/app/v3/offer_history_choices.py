"""Closed caller declarations; no legacy history/date/window defaults."""

from datetime import date
from typing import Any

from app.v3.offer_history_models import TARGET_UNIT, OfferHistoryChoices, OfferProvenance
from app.v3.workload_policy import fields, integer
from app.v3.workload_validation import name


def validate_choices(value: OfferHistoryChoices) -> None:
    if type(value) is not OfferHistoryChoices or type(value.test_day) is not date:
        raise ValueError("Exact offered-history choices and calendar test_day required")
    if type(value.target_unit) is not str or value.target_unit != TARGET_UNIT:
        raise ValueError("Only outbound_whole_hu_offers is accepted")
    name(value.timezone_name)
    start = integer(value.window_start_second)
    end = integer(value.window_end_second)
    if not 0 <= start < end <= 86400 or end - start != 28800:
        raise ValueError("Explicit equal local eight-hour observation window required")
    p = value.provenance
    if type(p) is not OfferProvenance or type(p.kind) is not str or p.kind != "declared_synthetic":
        raise ValueError("Only explicitly declared synthetic whole-HU history is supported")
    for text in (p.dataset_id, p.generator_id, p.generator_version):
        name(text)
    if p.seed is not None:
        integer(p.seed)


def choices_record(value: OfferHistoryChoices) -> dict[str, Any]:
    p = value.provenance
    return {
        "target_unit": value.target_unit,
        "test_day": value.test_day.isoformat(),
        "timezone_name": value.timezone_name,
        "window_start_second": value.window_start_second,
        "window_end_second": value.window_end_second,
        "provenance": {
            "kind": p.kind,
            "dataset_id": p.dataset_id,
            "generator_id": p.generator_id,
            "generator_version": p.generator_version,
            "seed": p.seed,
        },
    }


def parse_choices(value: object) -> OfferHistoryChoices:
    row = fields(
        value,
        {
            "target_unit",
            "test_day",
            "timezone_name",
            "window_start_second",
            "window_end_second",
            "provenance",
        },
    )
    p = fields(
        row["provenance"], {"kind", "dataset_id", "generator_id", "generator_version", "seed"}
    )
    day_text = name(row["test_day"])
    day = date.fromisoformat(day_text)
    if day.isoformat() != day_text:
        raise ValueError("Canonical calendar date required")
    result = OfferHistoryChoices(
        row["target_unit"],
        day,
        row["timezone_name"],
        row["window_start_second"],
        row["window_end_second"],
        OfferProvenance(
            p["kind"], p["dataset_id"], p["generator_id"], p["generator_version"], p["seed"]
        ),
    )
    validate_choices(result)
    return result
