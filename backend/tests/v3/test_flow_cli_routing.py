"""Public command routing keeps verified component status and failure semantics."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.v3 import cli


@pytest.mark.parametrize("status,expected_code", [("complete", 0), ("partial", 1)])
def test_simulate_light_routes_explicit_paths_and_preserves_partial_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    inputs, profile, output = tmp_path / "inputs", tmp_path / "profile.json", tmp_path / "out"
    calls = []

    def simulate(bundle: Path, proposal: Path, target: Path) -> dict[str, Any]:
        calls.append((bundle, proposal, target))
        return {
            "status": status,
            "run_id": "verified-component",
            "capabilities": {"full_v3_warehouse": False},
        }

    monkeypatch.setattr(cli, "simulate_light_file", simulate, raising=False)
    code = cli.main(
        ["simulate-light", "--inputs", str(inputs), "--profile", str(profile), "--out", str(output)]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == expected_code and report["status"] == status
    assert calls == [(inputs, profile, output)]
    assert report["run_id"] == "verified-component"
    assert report["operational_admission"] is False


def test_simulate_light_reports_validation_error_without_success_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def invalid(bundle: Path, proposal: Path, target: Path) -> dict[str, Any]:
        raise ValueError("source profile rejected")

    monkeypatch.setattr(cli, "simulate_light_file", invalid, raising=False)
    output = tmp_path / "out"
    code = cli.main(["simulate-light", "--profile", "bad.json", "--out", str(output)])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["status"] == "failed"
    assert "source profile rejected" in report["error"]["message"]
    assert not output.exists()


def test_simulate_light_rejects_existing_output_before_component_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(bundle: Path, proposal: Path, target: Path) -> dict[str, Any]:
        pytest.fail("existing output must reject before execution")

    monkeypatch.setattr(cli, "simulate_light_file", forbidden, raising=False)
    output = tmp_path / "out"
    output.mkdir()
    (output / "keep").write_bytes(b"unchanged")
    code = cli.main(["simulate-light", "--profile", "example.json", "--out", str(output)])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["error"]["code"] == "output_not_empty"
    assert (output / "keep").read_bytes() == b"unchanged"
