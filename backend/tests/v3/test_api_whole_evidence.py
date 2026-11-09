"""Outer CLI result values cannot contradict the native publication they accompany."""

from copy import deepcopy

import pytest

from app.v3.api_whole_evidence import check_result
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.interface import Json


def values() -> tuple[Json, Json, Json]:
    run: Json = {
        "status": "partial",
        "run_id": "a" * 64,
        "input_hash": "b" * 64,
        "physical_input_hash": "c" * 64,
        "metrics": {"paid_ticks": 47},
        "capabilities": {"full_v3": False},
    }
    manifest: Json = {"event_chunks": [{}], "checkpoint_chunks": [{}, {}]}
    result: Json = {
        **deepcopy(run),
        "request_sha256": "d" * 64,
        "manifest_sha256": "e" * 64,
        "event_chunks": 1,
        "checkpoint_chunks": 2,
        "layout_version": LAYOUT_VERSION,
        "operational_admission": False,
        "request": "old/portable/request.json",
        "manifest": "old/portable/run/manifest.json",
    }
    return run, manifest, result


def test_exact_native_result_allows_portable_provenance_paths() -> None:
    run, manifest, result = values()
    check_result(result, run, manifest, "d" * 64, "e" * 64)


@pytest.mark.parametrize("field", ["status", "metrics", "capabilities", "count", "request"])
def test_rehashed_result_semantics_must_still_match_native_facts(field: str) -> None:
    run, manifest, result = values()
    if field == "status":
        result["status"] = "complete"
    elif field == "metrics":
        result["metrics"]["paid_ticks"] = 48
    elif field == "capabilities":
        result["capabilities"]["full_v3"] = True
    elif field == "count":
        result["event_chunks"] = True
    else:
        result["request_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        check_result(result, run, manifest, "d" * 64, "e" * 64)
