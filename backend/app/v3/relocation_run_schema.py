"""Closed opt-in N1 envelope; original coordinator publication is unchanged."""

from typing import Any

from app.v3.relocation_models import RELOCATION_VERSION

PUBLICATION_VERSION = "qoima-relocation-run-0.1.0"
TRANSPORT_VERSION = "qoima-relocation-run-bundle-0.1.0"
RUN_FIELDS = frozenset(
    {
        "schema_version",
        "engine_version",
        "run_id",
        "input_hash",
        "common_input_hash",
        "registry_common_hash",
        "horizon_tick",
        "end_tick_limit",
        "observed_until_tick",
        "status",
        "metrics",
        "outcome",
        "outcome_kind",
    }
)


def envelope(value: object) -> dict[str, Any]:
    if type(value) is not dict or value.keys() != RUN_FIELDS:
        raise ValueError("Relocation run envelope has missing or unknown fields")
    for key, expected in (
        ("schema_version", PUBLICATION_VERSION),
        ("engine_version", RELOCATION_VERSION),
    ):
        if type(value[key]) is not str or value[key] != expected:
            raise ValueError("Unsupported relocation publication or engine version")
    for key in ("run_id", "input_hash", "common_input_hash", "registry_common_hash"):
        text = value[key]
        if (
            type(text) is not str
            or len(text) != 64
            or any(c not in "0123456789abcdef" for c in text)
        ):
            raise ValueError("Relocation identity requires an exact lowercase SHA256")
    for key in ("horizon_tick", "end_tick_limit", "observed_until_tick"):
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("Relocation boundary requires an exact nonnegative integer")
    if type(value["status"]) is not str or value["status"] not in {"complete", "partial"}:
        raise ValueError("Unknown relocation operational status")
    if type(value["outcome_kind"]) is not str or value["outcome_kind"] not in {
        "relocation",
        "base_noop",
    }:
        raise ValueError("Unknown relocation outcome scope")
    if type(value["metrics"]) is not dict or type(value["outcome"]) is not dict:
        raise ValueError("Relocation metrics and native outcome require objects")
    return value
