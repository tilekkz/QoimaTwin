"""Correlated file tampering and failure preservation, without actual native execution."""

from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import api_forecast_relocation_validation as validation
from app.v3 import api_forecast_relocation_worker as worker
from app.v3.api_forecast_relocation_storage import checked
from app.v3.forecast_relocation_models import ForecastRelocationInputs
from app.v3.offer_planning_cli_storage import descriptor, put
from tests.v3.test_api_forecast_relocation import (
    Case,
    api_case,
    case,
    no_legacy_bootstrap,
    prepared_value,
    submit,
)

__all__ = ["api_case", "case", "no_legacy_bootstrap"]


@pytest.mark.parametrize("mutation", ["missing", "extra", "other_arm", "report", "outer"])
def test_rehashed_native_or_outer_substitution_rejects(case: Case, mutation: str) -> None:
    result = submit(case).json()
    _, raw = checked(case.api.store, result["run_id"])
    if mutation == "missing":
        del raw["pair/candidate/catalog.json"]
    elif mutation == "extra":
        raw["unexpected.json"] = b"{}"
    elif mutation == "other_arm":
        prefix = "pair/candidate/"
        raw[prefix + "inputs.json"] = b'{"arm":"independently-valid-other-candidate"}'
        manifest = parse_json(raw[prefix + "manifest.json"])
        manifest["inputs"] = descriptor("inputs.json", raw[prefix + "inputs.json"])
        raw[prefix + "manifest.json"] = canonical_bytes(manifest)
    elif mutation == "report":
        report = parse_json(raw["pair/comparison.json"])
        report["no_op"] = 1
        raw["pair/comparison.json"] = canonical_bytes(report)
    else:
        raw["inputs.json"] = b'{"other":"valid-outer"}'
    with pytest.raises((ValueError, KeyError)):
        validation.validate_output(raw, prepared_value(case.prepared))


def test_executor_failure_preserves_frozen_inputs_and_partial_files(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(value: ForecastRelocationInputs, root: Path) -> dict[str, Any]:
        root.mkdir()
        (root / "partial.txt").write_bytes(b"actual partial producer evidence")
        raise RuntimeError("executor stopped")

    monkeypatch.setattr(worker, "compare_forecast_relocation", fail)
    assert submit(case).status_code == 500
    attempts = list(case.api.store.root.glob("forecast-relocation-v3-evidence/attempt-*"))
    assert len(attempts) == 1
    assert (attempts[0] / "decision.json").exists() and (
        attempts[0] / "common-inputs.json"
    ).exists()
    assert (attempts[0] / "output/partial.txt").read_bytes() == b"actual partial producer evidence"
    assert (
        parse_json((attempts[0] / "failure.json").read_bytes())["partial_outputs_preserved"] is True
    )
    assert len(list((case.api.store.root / "runs").glob("*"))) == 1  # planning publication only


def test_failed_input_freeze_never_calls_executor(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = put

    def fail(root: Path, name: str, raw: bytes) -> dict[str, Any]:
        if name == "common-inputs.json":
            raise OSError("storage unavailable")
        return original(root, name, raw)

    monkeypatch.setattr(worker, "put", fail)
    assert submit(case).status_code == 500
    assert not case.executed


def test_warm_raw_corruption_blocks_all_public_returns(case: Case) -> None:
    result = submit(case).json()
    row = next(r for r in result["files"] if r["path"] == "pair/candidate/catalog.json")
    case.api.store.path("run_files", row["sha256"]).write_bytes(b"corrupt")
    assert submit(case).status_code == 500
    url = "/api/v3/forecast-relocation-runs/" + result["run_id"]
    assert case.api.client.get(url + "/result").status_code == 500
    assert case.api.client.get(url + "/files/" + row["sha256"]).status_code == 500
    assert len(case.executed) == 1
