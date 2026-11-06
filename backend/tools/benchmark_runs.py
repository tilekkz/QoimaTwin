"""Run from backend/: uv run python PATH/benchmark_runs.py --out D:/QoimaTwin-runs/NAME.

Produces two independent one-hour runs for each offered-load profile. Runtime measurements
are observations, not performance assertions; only 240/600 offered orders are spec oracles.
The output directory must be new and outside the repository. No history generation is timed.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.contracts.loader import ContractBundle
    from app.data.scenario_materializer import Profile
    from app.simulation.context import RunInputs
    from app.simulation.engine import Engine, RunOutcome

type Json = dict[str, Any]
PROFILES: tuple[tuple[Profile, int], ...] = (("large-normal", 240), ("large-peak", 600))
HORIZON_S = 3600


def _write_json(path: Path, value: object) -> None:
    from app.storage.canonical_json import canonical_bytes

    path.write_bytes(canonical_bytes(value))


def _source_state() -> Json:
    from app.storage.canonical_json import sha256_hex

    backend = Path.cwd().resolve()
    files = {
        path.relative_to(backend).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((backend / "app").rglob("*.py"))
    }
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "app_source_sha256": sha256_hex(files),
        "app_source_file_count": len(files),
        "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _runtime() -> Json:
    from app.storage.canonical_json import sha256_hex
    from app.version import ENGINE_VERSION

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    details = {
        "python": sys.version,
        "python_executable": sys.executable,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "engine_version": ENGINE_VERSION,
        "git_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        **_source_state(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "simpy", "pydantic", "jsonschema")
        },
    }
    return {**details, "fingerprint_sha256": sha256_hex(details)}


def _inputs(bundle: ContractBundle, profile: Profile, out_dir: Path) -> RunInputs:
    from app.contracts.assignment import Assignment
    from app.contracts.scenario import Scenario
    from app.data.scenario_materializer import materialize
    from app.simulation.context import RunInputs

    scenario = materialize(profile, HORIZON_S, bundle.config).scenario
    path = out_dir / "scenario.json"
    _write_json(path, scenario.model_dump(mode="json"))
    # Run the persisted immutable input, rather than an unrecorded in-memory variant.
    scenario = Scenario.from_json_text(path.read_bytes())
    assignment = Assignment.from_json_text(
        (bundle.directory / "assignment.example.json").read_bytes()
    )
    return RunInputs(bundle.layout, bundle.config, bundle.actors, assignment, scenario)


def _export(engine: Engine, outcome: RunOutcome, out_dir: Path) -> tuple[Json, Json, Json]:
    from app.exporter.identity import fingerprint
    from app.exporter.run import export_run, write_run
    from app.simulation.metrics_summary import summary as metrics_summary

    summary = metrics_summary(engine, outcome)
    run = export_run(engine, outcome)
    manifest = write_run(
        run,
        out_dir,
        metadata={
            "identity": fingerprint(engine.ctx.inputs),
            "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
            "metrics": summary,
            "provenance": engine.ctx.inputs.scenario.provenance.model_dump(mode="json"),
            "ticks_per_second": engine.ctx.grid.ticks_per_second,
        },
    )
    return run, manifest, summary


def _sizes(out_dir: Path, manifest: Json) -> dict[str, int]:
    chunks = sum((out_dir / chunk["path"]).stat().st_size for chunk in manifest["chunks"])
    catalog = (out_dir / manifest["catalog"]["path"]).stat().st_size
    return {
        "inline_bytes": (out_dir / "run.json").stat().st_size,
        "chunks_only_bytes": chunks,
        "chunk_bundle_bytes": chunks + catalog + (out_dir / "manifest.json").stat().st_size,
        "all_files_bytes": sum(
            path.stat().st_size for path in out_dir.rglob("*") if path.is_file()
        ),
    }


def _measure(bundle: ContractBundle, profile: Profile, expected: int, out_dir: Path) -> Json:
    from app.exporter.events import project_events
    from app.simulation.engine import Engine
    from app.storage.canonical_json import sha256_hex

    out_dir.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    inputs = _inputs(bundle, profile, out_dir)
    materialization_s = perf_counter() - started
    started = perf_counter()
    engine = Engine(inputs, check_invariants=True)
    construction_s = perf_counter() - started
    started = perf_counter()
    outcome = engine.run()
    run_s = perf_counter() - started
    started = perf_counter()
    run, manifest, summary = _export(engine, outcome, out_dir)
    export_s = perf_counter() - started
    events_hash = sha256_hex(run["events"])
    projected_hash = sha256_hex(project_events(engine))
    checks = {
        "offered_count": len(inputs.scenario.orders) == expected,
        "arrived_count": engine.metrics.counts()["arrived_total"] == expected,
        "invariants": not engine.ctx.ledger.check_conservation(),
        "projection_hash_matches_export": projected_hash == events_hash,
    }
    return {
        "path": str(out_dir),
        "run_id": run["run_id"],
        "events_sha256": events_hash,
        "scenario_sha256": sha256_hex(inputs.scenario.model_dump(mode="json")),
        "status": outcome.status.value,
        "termination_reason": outcome.termination.value,
        "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
        "timings_s": {
            "materialization": materialization_s,
            "construction": construction_s,
            "run": run_s,
            "export_including_metrics_validation_and_io": export_s,
        },
        "sizes": _sizes(out_dir, manifest),
        "snapshot_count": len(run["snapshots"]),
        "event_count": len(run["events"]),
        "action_count": len(run["actions"]),
        "chunk_count": len(manifest["chunks"]),
        "metrics": summary,
        "checks": checks,
    }


def _profile(bundle: ContractBundle, profile: Profile, expected: int, out_dir: Path) -> Json:
    measurements = []
    for iteration in (1, 2):
        print(f"{profile}: run {iteration}/2", flush=True)
        measurements.append(_measure(bundle, profile, expected, out_dir / f"run-{iteration}"))
        gc.collect()
    first, second = measurements
    deterministic = {
        name: first[name] == second[name]
        for name in ("run_id", "events_sha256", "scenario_sha256", "metrics")
    }
    passed = all(deterministic.values()) and all(
        all(measurement["checks"].values()) for measurement in measurements
    )
    return {
        "offered_orders_expected_from_spec": expected,
        "deterministic": deterministic,
        "passed": passed,
        "runs": measurements,
    }


def _output(path: Path) -> Path:
    out_dir = path.expanduser().resolve()
    repository = Path.cwd().resolve().parent
    if out_dir == repository or repository in out_dir.parents:
        raise ValueError("benchmark output must be outside the repository")
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def main() -> int:
    from app.contracts.loader import load_contract_bundle
    from app.settings import default_contracts_dir

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out_dir = _output(args.out)
    report: Json = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "runtime": _runtime(),
        "horizon_s": HORIZON_S,
        "profiles": {},
        "status": "running",
        "size_semantics": {
            "inline_bytes": "raw run.json only",
            "chunk_bundle_bytes": "manifest + catalog + referenced chunks; no inline or inputs",
            "all_files_bytes": "all files per run, including scenario, inline and chunk bundle",
        },
    }
    try:
        bundle = load_contract_bundle(default_contracts_dir())
        for profile, expected in PROFILES:
            report["profiles"][profile] = _profile(bundle, profile, expected, out_dir / profile)
            _write_json(out_dir / "benchmark.json", report)
        report["status"] = (
            "passed" if all(p["passed"] for p in report["profiles"].values()) else "failed"
        )
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    _write_json(out_dir / "benchmark.json", report)
    print(json.dumps({"status": report["status"], "report": str(out_dir / "benchmark.json")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path.cwd()))
    raise SystemExit(main())
