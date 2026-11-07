"""All command failures are JSON, and no command overwrites an existing bundle."""

import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd  # type: ignore[import-untyped]
import pytest

from app.cli import main
from app.contracts.loader import ContractBundle
from app.exporter.validation import validate_run
from app.simulation.recorder import RecorderError


@pytest.mark.parametrize("command", ["simulate", "materialize"])
def test_existing_output_is_rejected_before_work(
    command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "keep").write_text("original", encoding="utf-8")
    assert (
        main([command, "--profile", "large-normal", "--horizon-s", "600", "--out", str(tmp_path)])
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "output_not_empty"
    assert (tmp_path / "keep").read_text(encoding="utf-8") == "original"


def test_invalid_cli_argument_is_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["simulate", "--profile", "invalid"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "invalid_input"


def test_excessive_horizon_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "simulate",
                "--profile",
                "large-normal",
                "--horizon-s",
                "604801",
                "--out",
                str(tmp_path),
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "invalid_input"
    assert "168" in report["error"]["message"]


@pytest.mark.parametrize("status,code", [("complete", 0), ("partial", 1), ("failed", 1)])
def test_simulation_status_controls_exit_code(
    status: str,
    code: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("app.cli.simulate", lambda *_: {"status": status})
    assert (
        main(
            ["simulate", "--profile", "large-normal", "--horizon-s", "600", "--out", str(tmp_path)]
        )
        == code
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == status
    assert result["layout_version"] == "qoima-72x48-v2"
    assert result["contracts_dir"]


@pytest.mark.parametrize("error", [KeyError("missing"), RecorderError("overlapping action")])
def test_execution_exceptions_are_json_without_tracebacks(
    error: Exception,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_args: object) -> None:
        raise error

    monkeypatch.setattr("app.cli.simulate", fail)
    assert (
        main(
            ["simulate", "--profile", "large-normal", "--horizon-s", "600", "--out", str(tmp_path)]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert not captured.err
    assert json.loads(captured.out)["error"]["code"] == "execution_error"


def test_assignment_layout_mismatch_fails_before_publication(
    bundle: ContractBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = json.loads((bundle.directory / "assignment.example.json").read_bytes())
    payload["layout_version"] = "wrong-layout"
    assignment = tmp_path / "assignment.json"
    assignment.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("app.cli_simulation.write_materialized", lambda *_: None)
    out = tmp_path / "output"
    assert (
        main(
            [
                "simulate",
                "--profile",
                "large-normal",
                "--horizon-s",
                "1",
                "--out",
                str(out),
                "--assignment",
                str(assignment),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_input"
    assert not out.exists()


def test_simulate_publishes_inputs_then_validated_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # History generation has separate artifact tests; keep this CLI boundary case small.
    monkeypatch.setattr(
        "app.data.scenario_materializer.generate_history", lambda: pd.DataFrame({"visits": [1]})
    )
    validator = Mock(wraps=validate_run)
    monkeypatch.setattr("app.exporter.run.validate_run", validator)
    assert (
        main(["simulate", "--profile", "large-normal", "--horizon-s", "15", "--out", str(tmp_path)])
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "complete"
    assert report["shortened_run"] is True
    scenario = json.loads((tmp_path / "inputs/scenario.json").read_bytes())
    assert len(scenario["orders"]) == 1  # one arrival at 7.5 seconds
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    assert manifest["run_id"] == report["run_id"]
    assert manifest["chunk_duration_s"] == 60
    assert manifest["snapshot_interval_s"] == 30
    assert validator.call_count == 1
