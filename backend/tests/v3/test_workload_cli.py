"""Publish frozen timed offers without granting execution or allocating stock."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.v3.cli import main

EXAMPLE = Path("docs/proposals/adaptive-v3/workload-policy.example.json")


def invoke(policy: Path, output: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    code = main(["materialize-workload", "--policy", str(policy), "--out", str(output)])
    result: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert code == 0, result
    return result


def test_cli_publishes_frozen_source_and_identical_artifacts_across_output_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    one, two = invoke(EXAMPLE, first, capsys), invoke(EXAMPLE, second, capsys)
    assert one == two and one["status"] == "passed"
    assert one["data_kind"] == "synthetic_timed_workload" and not one["operational_admission"]
    manifest = json.loads((first / "manifest.json").read_bytes())
    for entry in manifest["files"]:
        raw = (first / entry["path"]).read_bytes()
        assert raw == (second / entry["path"]).read_bytes()
        assert len(raw) == entry["bytes"] and sha256(raw).hexdigest() == entry["sha256"]
    workload = json.loads((first / "workload.json").read_bytes())
    assert workload["workload_id"] == one["workload_id"]
    assert len(workload["source"]["templates"]) == 200
    assert sum(len(t["initial_hu_ids"]) for t in workload["source"]["templates"]) == 530
    assert len(workload["jobs"]) == 20
    assert all(job["hu_id"] is None for job in workload["jobs"] if job["direction"] == "outbound")


@pytest.mark.parametrize("horizon", [True, -1, 1.5])
def test_cli_rejects_malformed_policy_without_publishing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    horizon: object,
) -> None:
    data = json.loads(EXAMPLE.read_bytes())
    data["horizon_tick"] = horizon
    policy, output = tmp_path / "policy.json", tmp_path / "output"
    policy.write_text(json.dumps(data), encoding="utf-8")
    code = main(["materialize-workload", "--policy", str(policy), "--out", str(output)])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["status"] == "failed"
    assert not (output / "manifest.json").exists()


def test_cli_never_overwrites_existing_workload_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_bytes(b"unchanged")
    code = main(["materialize-workload", "--policy", str(EXAMPLE), "--out", str(output)])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["error"]["code"] == "output_not_empty"
    assert (output / "keep.txt").read_bytes() == b"unchanged"
