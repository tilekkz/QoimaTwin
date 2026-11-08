"""Closed C publication envelope; native records have a separate exact typed codec."""

from typing import Any

PUBLICATION_VERSION = "qoima-coordinator-run-0.2.0"
TRANSPORT_VERSION = "qoima-coordinator-run-bundle-0.1.0"
RUN_FIELDS = frozenset(
    {
        "schema_version",
        "engine_version",
        "run_id",
        "input_hash",
        "registry_common_hash",
        "horizon_tick",
        "end_tick_limit",
        "observed_until_tick",
        "status",
        "metrics",
        "outcome",
    }
)


def envelope(value: object) -> dict[str, Any]:
    if type(value) is not dict or value.keys() != RUN_FIELDS:
        raise ValueError("Coordinator run envelope has missing or unknown fields")
    if value["schema_version"] != PUBLICATION_VERSION:
        raise ValueError("Unsupported coordinator publication version")
    for key in ("run_id", "input_hash", "registry_common_hash"):
        text = value[key]
        if (
            type(text) is not str
            or len(text) != 64
            or any(c not in "0123456789abcdef" for c in text)
        ):
            raise ValueError("Coordinator identity requires an exact lowercase SHA256")
    for key in ("horizon_tick", "end_tick_limit", "observed_until_tick"):
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("Coordinator boundary requires an exact nonnegative integer")
    if type(value["status"]) is not str or value["status"] not in {"complete", "partial"}:
        raise ValueError("Unknown coordinator operational status")
    if type(value["metrics"]) is not dict or type(value["outcome"]) is not dict:
        raise ValueError("Coordinator metrics and native outcome require objects")
    return value
