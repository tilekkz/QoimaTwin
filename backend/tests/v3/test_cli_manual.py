"""The explicit manual proposal materializes inputs before producing an actual run."""

import json
from pathlib import Path

import pytest

from app.cli import main
from app.v3 import cli

PROFILE = Path(__file__).parents[2] / "data/v3-execution-proposals/manual-whole-hu-demo-v1.json"


def test_materialize_manual_has_no_engine_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["v3", "materialize-manual", "--profile", str(PROFILE), "--out", str(tmp_path)]) == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["jobs"] == 4
    assert (tmp_path / "materialized.json").is_file()
    assert (tmp_path / "graph.json").is_file()
    assert not (tmp_path / "run").exists()


def test_manual_cli_executes_declared_flow_and_exports_replay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["v3", "simulate-manual", "--profile", str(PROFILE), "--out", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "complete"
    assert report["source_label"] == "actual_engine_run"
    assert not report["full_v3_warehouse"]
    assert (tmp_path / "inputs/materialized.json").is_file()
    assert (tmp_path / "run/manifest.json").is_file()
    metrics = json.loads((tmp_path / "metrics.json").read_bytes())
    assert metrics["at_end"]["inbound"]["completed_hus"] == 2
    assert metrics["at_end"]["outbound"]["completed_hus"] == 2


def test_manual_cli_does_not_overwrite_existing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = tmp_path / "keep.txt"
    marker.write_text("keep", encoding="ascii")
    assert main(["v3", "simulate-manual", "--profile", str(PROFILE), "--out", str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "output_not_empty"
    assert marker.read_text(encoding="ascii") == "keep"


def test_manual_cli_reports_runtime_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_run(bundle_path: Path, profile_path: Path, out: Path) -> dict[str, object]:
        raise RuntimeError("manual conservation check failed")

    monkeypatch.setattr(cli, "simulate_manual", broken_run)
    assert main(["v3", "simulate-manual", "--profile", str(PROFILE), "--out", str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert report["error"]["code"] == "execution_error"
