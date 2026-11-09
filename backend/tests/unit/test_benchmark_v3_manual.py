"""Fast benchmark protocol tests; never a source-scale performance measurement."""

import copy
import importlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.unit.benchmark_v3_fixture import tiny_inputs
from tools import benchmark_v3_counters as counters
from tools import benchmark_v3_manual as bench
from tools.benchmark_v3_counters import peak_rss_bytes, timed
from tools.benchmark_v3_evidence import (
    IDENTITY_KEYS,
    artifact_inventory,
    determinism,
    digest,
    source_state,
)


def options(root: Path) -> list[str]:
    return [
        "--bundle",
        str(root / "bundle"),
        "--proposal",
        str(root / "proposal.json"),
        "--out",
        str(root / "output"),
        "--iterations",
        "2",
    ]


@pytest.mark.parametrize("iterations", ["0", "1", "-1"])
def test_repeats_require_at_least_two(tmp_path: Path, iterations: str) -> None:
    argv = options(tmp_path)
    argv[-1] = iterations
    with pytest.raises(SystemExit):
        bench.arguments(argv)


def test_output_preserves_existing_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "output"
    out.mkdir()
    artifact = out / "manifest.json"
    artifact.write_text("immutable")
    with pytest.raises(ValueError, match="empty"):
        bench.prepare_output(out)
    assert artifact.read_text() == "immutable"


def test_exact_event_hash_changes_subdisplay_motion() -> None:
    events: list[dict[str, Any]] = [
        {"tick": 1, "motion": {"length": {"numerator": 10000001, "denominator": 10000000}}}
    ]
    changed = copy.deepcopy(events)
    changed[0]["motion"]["length"]["numerator"] += 1
    assert digest(events) != digest(changed)


@pytest.mark.parametrize("mode", ["exit", "missing"])
def test_child_failure_is_not_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    def child(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 9 if mode == "exit" else 0, "", "boom")

    monkeypatch.setattr("tools.benchmark_v3_manual.subprocess.run", child)
    with pytest.raises(RuntimeError, match="worker"):
        bench.spawn(bench.arguments(options(tmp_path)), tmp_path, 1)


def test_source_fingerprint_is_allowlisted(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    source = app / "public.py"
    source.write_text("x = 1")
    (tmp_path / ".env").write_text("excluded")
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "benchmark_v3_manual.py").write_text("pass")
    before = source_state(tmp_path)
    (tmp_path / ".env").write_text("still excluded")
    assert source_state(tmp_path) == before
    source.write_text("x = 2")
    assert source_state(tmp_path) != before


def test_counters_are_positive_and_timed_work_is_observed() -> None:
    value, timing = timed(lambda: sum(range(10000)))
    assert value == 49995000
    assert timing["wall_s"] > 0 and timing["cpu_s"] >= 0
    assert peak_rss_bytes() > 1024 * 1024


def test_determinism_requires_present_values_and_two_repeats() -> None:
    with pytest.raises(ValueError):
        determinism([{}])
    assert not all(determinism([{}, {}]).values())


def test_missing_artifact_rejected(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "x"}))
    with pytest.raises((KeyError, ValueError)):
        artifact_inventory(tmp_path)


def harness(root: Path, extra: str = "") -> Path:
    script = root / "tiny_worker.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(bench.BACKEND)!r})\n"
        "import app.v3.profile\n"
        "from tests.unit.benchmark_v3_fixture import tiny_inputs\n"
        "app.v3.profile.load_manual_profile = tiny_inputs\n"
        "from tools import benchmark_v3_manual as bench\n"
        + extra
        + "\nraise SystemExit(bench.main())\n",
        encoding="utf-8",
    )
    (root / "proposal.json").write_text("{}")
    return script


def test_real_fresh_children_engine_export_and_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bench, "SCRIPT", harness(tmp_path))
    assert bench.main(options(tmp_path)) == 0
    out = tmp_path / "output"
    report = json.loads((out / "benchmark.json").read_bytes())
    first, second = report["runs"]
    assert first["pid"] != second["pid"]
    assert first["scope"]["jobs"] == 1
    assert first["scope"]["initial_hus"] == 1
    assert first["scope"]["horizon_tick"] == 60000000
    assert first["operational_status"] == "complete"
    assert first["event_count"] > 0
    assert all(report["deterministic"].values())
    assert first["raw_export_bytes"] == sum(a["bytes"] for a in first["artifacts"].values())
    assert (
        first["timings"]["whole_child"]["cpu_s_since_process_launch"]
        >= sum(
            timing["cpu_s"] for name, timing in first["timings"].items() if name != "whole_child"
        )
        - 0.02
    )
    assert first["whole_child_wall_s_including_startup_shutdown"] > 0
    assert first["peak_rss_bytes_whole_process_including_compile_export"] > 0
    manifest = json.loads((out / "manifest.json").read_bytes())
    assert manifest["sha256"] == digest(report)
    assert (out / "latest.json").is_file()
    assert bench.main(options(tmp_path)) == 1
    assert json.loads((out / "manifest.json").read_bytes()) == manifest


@pytest.mark.parametrize("key", IDENTITY_KEYS)
def test_each_determinism_binding_rejects_mismatch(key: str) -> None:
    first = dict.fromkeys(IDENTITY_KEYS, "bound") | {"pid": 1}
    second = first | {key: "changed", "pid": 2}
    with pytest.raises(ValueError, match="mismatch"):
        bench.verify_results([first, second], {"source_sha256": "bound"}, "bound")


def test_worker_subprocess_nonzero_has_no_success_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = harness(tmp_path, "raise RuntimeError('deliberate child failure')")
    monkeypatch.setattr(bench, "SCRIPT", script)
    assert bench.main(options(tmp_path)) == 1
    assert not (tmp_path / "output" / "manifest.json").exists()
    assert not (tmp_path / "output" / "latest.json").exists()


def test_export_does_not_rerun_one_shot_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.v3.execution import ManualEngine

    original = ManualEngine.run
    calls = 0

    def counted(self: ManualEngine, horizon_tick: int, end_tick: int) -> Any:
        nonlocal calls
        calls += 1
        return original(self, horizon_tick, end_tick)

    monkeypatch.setattr(ManualEngine, "run", counted)
    inputs = tiny_inputs(tmp_path, tmp_path)
    details, timings, _, run = bench.execute(inputs, tmp_path)
    assert calls == 1
    assert details["events_sha256"] == digest(run["events"])
    assert {
        "engine_run",
        "schema_semantic_validation_extra_pass",
        "export_build_including_validation",
        "write_including_validation",
    } <= timings.keys()
    damaged = copy.deepcopy(run)
    damaged["events"][0]["tick"] += 1
    outcome = ManualEngine(inputs.profile, inputs.graph).run(inputs.horizon_tick, inputs.end_tick)
    with pytest.raises(ValueError, match="changed actual"):
        bench.identity(inputs, outcome, damaged)


def test_raw_file_corruption_is_rejected(tmp_path: Path) -> None:
    bench.execute(tiny_inputs(tmp_path, tmp_path), tmp_path)
    path = tmp_path / "export" / "metadata.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="raw bytes/hash"):
        artifact_inventory(tmp_path / "export")


@pytest.mark.parametrize("system,multiplier", [("linux", 1024), ("darwin", 1)])
def test_unix_peak_rss_units(monkeypatch: pytest.MonkeyPatch, system: str, multiplier: int) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr("tools.benchmark_v3_counters.sys.platform", system)
    monkeypatch.setattr("tools.benchmark_v3_counters.os.name", "posix")
    resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_maxrss=17))
    monkeypatch.setattr("tools.benchmark_v3_counters.importlib.import_module", lambda _: resource)
    assert counters.peak_rss_bytes() == 17 * multiplier


def test_partial_is_reported_without_claiming_complete(tmp_path: Path) -> None:
    inputs = tiny_inputs(tmp_path, tmp_path)
    inputs = replace(inputs, horizon_tick=1000000, end_tick=2000000)
    details, _, _, _ = bench.execute(inputs, tmp_path)
    assert details["operational_status"] == "partial"


def test_optional_metrics_absence_only_is_optional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.v3.execution import ManualEngine

    inputs = tiny_inputs(tmp_path, tmp_path)
    outcome = ManualEngine(inputs.profile, inputs.graph).run(inputs.horizon_tick, inputs.end_tick)

    def missing(name: str) -> None:
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr(importlib, "import_module", missing)
    assert bench.optional_metrics(inputs, outcome) is None

    def broken(name: str) -> None:
        raise ModuleNotFoundError(name="broken_dependency")

    monkeypatch.setattr(importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError):
        bench.optional_metrics(inputs, outcome)


def test_mismatch_prevents_success_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = dict.fromkeys(IDENTITY_KEYS, "bound") | {"pid": 1}
    second = first | {"events_sha256": "changed", "pid": 2}
    runs = iter([first, second])
    monkeypatch.setattr(bench, "spawn", lambda *args: next(runs))
    monkeypatch.setattr(bench, "source_state", lambda *args: {"source_sha256": "bound"})
    monkeypatch.setattr(bench, "revision", lambda: "bound")
    assert bench.main(options(tmp_path)) == 1
    assert not (tmp_path / "output" / "latest.json").exists()
    assert not (tmp_path / "output" / "manifest.json").exists()


def test_cli_requires_explicit_paths() -> None:
    with pytest.raises(SystemExit):
        bench.arguments(["--out", "unused"])
