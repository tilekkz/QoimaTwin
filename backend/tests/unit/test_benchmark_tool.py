"""Benchmark orchestration checks without running load tests during the unit gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from app.contracts.loader import ContractBundle
from app.exporter.validation import validate_run
from app.storage.canonical_json import parse_json
from tests.builders import scenario
from tools import benchmark_runs as bench


def test_options_default_to_two_hourly_profiles(tmp_path: Path) -> None:
    args = bench._arguments(["--out", str(tmp_path / "report")])
    assert (args.horizon_s, args.iterations, args.format) == (3600, 2, "v2")
    assert args.profiles == ["large-normal", "large-peak"]


def test_options_accept_shift_and_selected_profile(tmp_path: Path) -> None:
    args = bench._arguments(
        ["--out", str(tmp_path), "--horizon-s", "28800", "--profiles", "large-peak"]
    )
    assert args.horizon_s == 28800
    assert args.profiles == ["large-peak"]


@pytest.mark.parametrize("flag,value", [("--iterations", "0"), ("--horizon-s", "604801")])
def test_invalid_options_fail(flag: str, value: str, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        bench._arguments(["--out", str(tmp_path), flag, value])
    assert exc.value.code == 2


def test_offered_count_comes_from_rate_and_half_open_horizon() -> None:
    assert bench._expected_orders("large-normal", 28800) == 1920
    assert bench._expected_orders("large-peak", 28800) == 4800
    assert bench._expected_orders("large-peak", 3) == 0  # First midpoint is exactly at H.
    assert bench._expected_orders("large-peak", 4) == 1


def test_one_iteration_does_not_claim_determinism() -> None:
    measurement = dict.fromkeys(("run_id", "events_sha256", "scenario_sha256", "metrics"), 1)
    assert set(bench._determinism([measurement]).values()) == {None}
    assert set(bench._determinism([measurement, measurement]).values()) == {True}
    changed = {**measurement, "events_sha256": 2}
    assert bench._determinism([measurement, changed])["events_sha256"] is False


def test_peak_resident_memory_is_positive_bytes() -> None:
    assert bench._peak_rss_bytes() > 1024 * 1024


def test_each_iteration_spawns_worker_with_isolated_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = bench._arguments(["--out", str(tmp_path)])
    commands: list[list[str]] = []

    def child(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        path = Path(command[command.index("--worker-report") + 1])
        path.write_text(json.dumps({"pid": len(commands), "checks": {"ok": True}}))
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("tools.benchmark_runs.subprocess.run", child)
    first = bench._spawn_measurement(args, "large-normal", tmp_path, 1)
    second = bench._spawn_measurement(args, "large-normal", tmp_path, 2)
    assert first["pid"] != second["pid"]
    assert commands[0] != commands[1]
    assert "--worker" in commands[0]


def test_worker_failure_preserves_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = bench._arguments(["--out", str(tmp_path)])
    monkeypatch.setattr(
        "tools.benchmark_runs.subprocess.run",
        Mock(return_value=subprocess.CompletedProcess([], 1, "", "worker failed")),
    )
    with pytest.raises(RuntimeError, match="worker failed"):
        bench._spawn_measurement(args, "large-normal", tmp_path, 1)


def test_scenario_is_persisted_under_owned_inputs(
    bundle: ContractBundle, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixed = scenario([], horizon_s=600)
    monkeypatch.setattr(
        "app.data.scenario_materializer.materialize",
        Mock(return_value=SimpleNamespace(scenario=fixed)),
    )
    inputs = bench._inputs(bundle, "large-normal", 600, tmp_path)
    assert parse_json((tmp_path / "inputs/scenario.json").read_bytes()) == fixed.model_dump(
        mode="json"
    )
    assert not (tmp_path / "scenario.json").exists()
    assert inputs.scenario == fixed


def test_proposal_size_counts_referenced_payload_without_inline(tmp_path: Path) -> None:
    for name, size in [("events.json", 10), ("snapshots.json", 20), ("meta.json", 30)]:
        (tmp_path / name).write_bytes(b" " * size)
    (tmp_path / "manifest.json").write_bytes(b" " * 7)
    manifest = {
        "event_chunks": [{"path": "events.json"}],
        "snapshot_chunks": [{"path": "snapshots.json"}],
        "catalog": {"path": "meta.json"},
    }
    sizes = bench._sizes(tmp_path, manifest)
    assert sizes["inline_bytes"] == 0
    assert sizes["chunks_only_bytes"] == 30
    assert sizes["chunk_bundle_bytes"] == 67
    assert sizes["all_files_bytes"] == 67


def test_worker_publishes_tiny_validated_run_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixed = scenario([], horizon_s=1)
    monkeypatch.setattr(
        "app.data.scenario_materializer.materialize",
        Mock(return_value=SimpleNamespace(scenario=fixed)),
    )
    validator = Mock(wraps=validate_run)
    monkeypatch.setattr("app.exporter.run.validate_run", validator)
    args = bench._arguments(
        [
            "--worker",
            "--out",
            str(tmp_path / "run"),
            "--horizon-s",
            "1",
            "--profiles",
            "large-normal",
            "--worker-report",
            str(tmp_path / "measurement.json"),
        ]
    )
    assert bench._worker(args) == 0
    report = parse_json((tmp_path / "measurement.json").read_bytes())
    assert validator.call_count == 1
    assert report["status"] == "complete"
    assert all(report["checks"].values())
    assert report["sizes"]["chunk_bundle_bytes"] > 0
    assert report["timings"]["engine"]["wall_s"] >= 0
    assert report["timings"]["export_including_metrics_validation_and_io"]["cpu_s"] >= 0
    assert (tmp_path / "run/inputs/scenario.json").is_file()
