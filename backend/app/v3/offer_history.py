"""Fresh source-bound synthetic history authority; no default history generation."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.inputs import load_v3_bundle
from app.v3.offer_history_choices import parse_choices, validate_choices
from app.v3.offer_history_csv import read_counts
from app.v3.offer_history_models import OfferHistoryChoices, OfferHistoryInputs
from app.v3.offer_history_windows import observation_windows
from app.v3.offer_history_wire import history_record, normalized_hash
from app.v3.workload_policy import fields
from app.v3.workload_source import load_workload_source
from app.v3.workload_validation import name


def compile_offer_history(raw_history: bytes, choices: OfferHistoryChoices) -> OfferHistoryInputs:
    validate_choices(choices)
    windows = observation_windows(choices)
    root = Path(__file__).resolve().parents[2] / "data/v3-proposal"
    source = load_workload_source(load_v3_bundle(root))
    skus = tuple(t.sku_id for t in source.templates)
    if len(skus) != 200:
        raise ValueError("Pinned V3 history requires exactly 200 source SKUs")
    counts = read_counts(raw_history, skus, choices.test_day)
    value = OfferHistoryInputs(
        source,
        choices,
        raw_history,
        skus,
        counts,
        windows,
        sha256(raw_history).hexdigest(),
        "",
        b"",
        "",
    )
    value = replace(value, normalized_history_hash=normalized_hash(value))
    raw = canonical_bytes(history_record(value))
    return replace(value, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def load_offer_history(raw: bytes) -> OfferHistoryInputs:
    if type(raw) is not bytes:
        raise ValueError("Exact immutable history envelope bytes required")
    value = fields(
        parse_json(raw),
        {
            "version",
            "choices",
            "source",
            "raw_history_utf8",
            "raw_history_sha256",
            "normalized_history_hash",
            "sku_ids",
            "counts",
            "windows_utc",
            "maximum_exact_count",
            "operational_admission",
        },
    )
    expected = compile_offer_history(
        name(value["raw_history_utf8"]).encode("utf-8"), parse_choices(value["choices"])
    )
    if expected.frozen_bytes != raw:
        raise ValueError("History differs from fresh source, exact raw bytes or typed observations")
    return expected


def verify_offer_history(value: OfferHistoryInputs) -> OfferHistoryInputs:
    if type(value) is not OfferHistoryInputs:
        raise ValueError("Exact OfferHistoryInputs required")
    expected = load_offer_history(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
