"""A separately identified read model must never validate or replace native history."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.storage_fullness_publication import build_fullness_report, validate_fullness_report
from tests.v3.test_coordinator_seek_fixtures import case


def test_report_binds_native_bytes_without_mutating_run_or_claiming_source_capacities() -> None:
    inputs, run, _ = case("roles")
    before = canonical_bytes(run)
    result = build_fullness_report(run, inputs=inputs.frozen_bytes)
    assert result["source_run_id"] == run["run_id"]
    assert result["input_hash"] == inputs.input_hash
    assert result["native_run_sha256"] == sha256_hex(run)
    assert result["at_horizon"]["available"] is False
    assert result["at_end"]["available"] is False
    assert result["operational_admission"] is False
    identity = {key: value for key, value in result.items() if key != "report_id"}
    assert result["report_id"] == sha256_hex(identity)
    assert canonical_bytes(run) == before
    validate_fullness_report(result, run, inputs=inputs.frozen_bytes)


@pytest.mark.parametrize("field", ["source_run_id", "input_hash", "native_run_sha256", "version"])
def test_rehashed_report_cannot_change_source_identity(field: str) -> None:
    inputs, run, _ = case("roles")
    result = build_fullness_report(run, inputs=inputs.frozen_bytes)
    result[field] = "changed"
    result["report_id"] = sha256_hex(
        {key: value for key, value in result.items() if key != "report_id"}
    )
    with pytest.raises(ValueError):
        validate_fullness_report(result, run, inputs=inputs.frozen_bytes)


def test_corrupt_native_metadata_is_rejected_before_projection() -> None:
    inputs, run, _ = case("roles")
    wrong = deepcopy(run)
    wrong["run_id"] = "0" * 64
    with pytest.raises(ValueError):
        build_fullness_report(wrong, inputs=inputs.frozen_bytes)


def test_report_numeric_alias_or_extra_field_is_not_hidden_by_rehash() -> None:
    inputs, run, _ = case("roles")
    for field, value in (("operational_admission", 0), ("made_up", True)):
        result = build_fullness_report(run, inputs=inputs.frozen_bytes)
        result[field] = value
        result["report_id"] = sha256_hex({k: v for k, v in result.items() if k != "report_id"})
        with pytest.raises(ValueError):
            validate_fullness_report(result, run, inputs=inputs.frozen_bytes)
