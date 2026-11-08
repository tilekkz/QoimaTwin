"""Pair CLI preserves two frozen inputs before calling the two-run comparison once."""

from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import cli_coordinator_pair
from app.v3.coordinator_pair_models import CoordinatorPairResult, PreparedCoordinatorPair
from tests.v3.test_coordinator_cli import compiled_source, coordinator_sources

__all__ = ["compiled_source", "coordinator_sources"]


def setup_pair(
    monkeypatch: pytest.MonkeyPatch,
    compiled_source: Any,
    tmp_path: Path,
) -> tuple[Path, Any]:
    compiled, conveyor = compiled_source
    choices = parse_json(compiled.frozen_bytes)["choices"]
    profile = tmp_path / "profile.json"
    profile.write_bytes(canonical_bytes(choices))
    prepared = PreparedCoordinatorPair("N0", compiled, compiled, compiled.input_hash)
    monkeypatch.setattr(cli_coordinator_pair, "load_v3_bundle", lambda _: object())
    monkeypatch.setattr(cli_coordinator_pair, "load_conveyor_source", lambda _: conveyor)
    monkeypatch.setattr(cli_coordinator_pair, "prepare_coordinator_pair", lambda *a, **k: prepared)
    return profile, prepared


def test_both_input_evidence_precedes_comparison_and_partial_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    compiled_source: Any,
    tmp_path: Path,
) -> None:
    profile, prepared = setup_pair(monkeypatch, compiled_source, tmp_path)
    out, calls = tmp_path / "paired", []

    def compare(*args: Any, **kwargs: Any) -> CoordinatorPairResult:
        assert (out / "baseline/inputs.json").read_bytes() == prepared.baseline.frozen_bytes
        assert (out / "candidate/inputs.json").read_bytes() == prepared.candidate.frozen_bytes
        assert (out / "request.json").is_file()
        calls.append(kwargs["scenario"])
        report = {
            "comparison_id": "b" * 64,
            "verdict": "not_demonstrated",
            "full_v3_acceptance": False,
            "baseline": {"status": "partial"},
            "candidate": {"status": "complete"},
        }
        return CoordinatorPairResult(
            canonical_bytes(report),
            canonical_bytes({"status": "partial"}),
            canonical_bytes({"status": "complete"}),
            prepared.baseline.frozen_bytes,
            prepared.candidate.frozen_bytes,
        )

    def writer(run: dict[str, Any], path: Path, *, inputs: bytes) -> dict[str, Any]:
        assert (path / "inputs.json").read_bytes() == inputs
        (path / "manifest.json").write_bytes(canonical_bytes(run))
        return run

    monkeypatch.setattr(cli_coordinator_pair, "compare_coordinator_profiles", compare)
    monkeypatch.setattr(cli_coordinator_pair, "write_coordinator_run", writer)
    result = cli_coordinator_pair.compare_coordinator_files(
        tmp_path,
        profile,
        profile,
        "N0",
        out,
    )
    assert calls == ["N0"]
    assert result["status"] == "partial"
    assert result["comparison"]["verdict"] == "not_demonstrated"
    assert result["comparison"]["full_v3_acceptance"] is False
    assert parse_json((out / "result.json").read_bytes()) == result


def test_pair_execution_failure_preserves_both_inputs_and_request(
    monkeypatch: pytest.MonkeyPatch,
    compiled_source: Any,
    tmp_path: Path,
) -> None:
    profile, prepared = setup_pair(monkeypatch, compiled_source, tmp_path)
    out = tmp_path / "failure"

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("explicit pair test double failure")

    monkeypatch.setattr(cli_coordinator_pair, "compare_coordinator_profiles", fail)
    result = cli_coordinator_pair.compare_coordinator_files(
        tmp_path,
        profile,
        profile,
        "N0",
        out,
    )
    assert result["status"] == "failed"
    assert (out / "candidate/inputs.json").read_bytes() == prepared.candidate.frozen_bytes
    assert (out / "baseline/inputs.json").read_bytes() == prepared.baseline.frozen_bytes
    assert parse_json((out / "result.json").read_bytes()) == result
