"""Benchmark only an explicit pinned V3 manual profile in fresh subprocesses.

No generated normal/peak workload or horizon override. See research protocol 11.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter, process_time
from typing import TYPE_CHECKING

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))

from tools.benchmark_v3_counters import peak_rss_bytes, timed  # noqa: E402
from tools.benchmark_v3_evidence import (  # noqa: E402
    Json,
    artifact_inventory,
    determinism,
    digest,
    exclusive_json,
    source_state,
)

if TYPE_CHECKING:
    from app.v3.execution_types import ManualOutcome
    from app.v3.profile import CompiledManualInputs


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.iterations < 2:
        parser.error("iterations must be >=2")
    return args


def prepare_output(path: Path) -> Path:
    out = path.resolve()
    if out == BACKEND.parent or BACKEND.parent in out.parents:
        raise ValueError("output must be outside the repository")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("output directory must be new or empty")
    out.mkdir(parents=True, exist_ok=True)
    return out


def revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=BACKEND, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def profile_scope(inputs: CompiledManualInputs) -> Json:
    p = inputs.profile
    return {
        "claim": "explicit supplied manual profile only; not full V3 normal/peak performance",
        "jobs": len(p.jobs),
        "inbound_jobs": sum(j.direction == "inbound" for j in p.jobs),
        "outbound_jobs": sum(j.direction == "outbound" for j in p.jobs),
        "initial_hus": len(p.initial_placements),
        "universe_hus": len(p.handling_units),
        "sku_count": len({hu.sku_id for hu in p.handling_units}),
        "actors": len(p.actors),
        "ports": len(p.ports),
        "buffers_per_port": {p.port_id: len(p.buffer_places) for p in p.ports},
        "executed_archetypes": sorted(
            {hu.archetype for hu in p.handling_units if hu.hu_id in {j.hu_id for j in p.jobs}}
        ),
        "horizon_tick": inputs.horizon_tick,
        "end_tick": inputs.end_tick,
        "arrival_ticks": [j.arrival_tick for j in p.jobs],
    }


def optional_metrics(inputs: CompiledManualInputs, outcome: ManualOutcome) -> Json | None:
    name = "app.v3.manual_metrics"
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name != name:
            raise
        return None
    result: Json = module.summary(inputs.profile, outcome)
    return result


def identity(inputs: CompiledManualInputs, outcome: ManualOutcome, run: Json) -> Json:
    from app.v3.execution_types import MANUAL_ENGINE_VERSION
    from app.v3.input_pin import SOURCE_REVISION
    from app.v3.run_values import record

    events = [record(event) for event in outcome.events]
    if run["events"] != events:
        raise ValueError("export changed actual engine events")
    if outcome.at_end.status not in {"complete", "partial"}:
        raise ValueError("engine returned a failed/unknown operational status")
    return {
        "run_id": run["run_id"],
        "events_sha256": digest(events),
        "profile_sha256": digest(record(inputs.profile)),
        "input_hash": inputs.input_hash,
        "graph_sha256": inputs.graph.sha256,
        "engine_version": MANUAL_ENGINE_VERSION,
        "source_revision": SOURCE_REVISION,
        "horizon_tick": inputs.horizon_tick,
        "end_tick": inputs.end_tick,
        "event_count": len(events),
        "operational_status": outcome.at_end.status,
    }


def execute(inputs: CompiledManualInputs, out: Path) -> tuple[Json, Json, Json | None, Json]:
    from app.v3.execution import ManualEngine
    from app.v3.run_export import build_manual_run, validate_manual_run
    from app.v3.run_transport import write_manual_run

    engine, construction = timed(
        lambda: ManualEngine(inputs.profile, inputs.graph, check_invariants=True)
    )
    outcome, engine_cost = timed(lambda: engine.run(inputs.horizon_tick, inputs.end_tick))
    run, export = timed(
        lambda: build_manual_run(
            inputs.profile,
            inputs.graph,
            outcome,
            graph_document=inputs.graph_document.decode(),
            end_tick_limit=inputs.end_tick,
        )
    )
    _, schema = timed(lambda: validate_manual_run(run))
    _, write = timed(lambda: write_manual_run(run, out / "export"))
    metrics, metric_cost = timed(lambda: optional_metrics(inputs, outcome))
    details = identity(inputs, outcome, run)
    timings = {
        "engine_construction": construction,
        "engine_run": engine_cost,
        "export_build_including_validation": export,
        "schema_semantic_validation_extra_pass": schema,
        "write_including_validation": write,
        "optional_metrics": metric_cost,
    }
    return details, timings, metrics, run


def measure(args: argparse.Namespace) -> Json:
    wall = perf_counter()
    from app.v3.profile import load_manual_profile

    before, git_revision = source_state(BACKEND), revision()
    proposal_hash = hashlib.sha256(args.proposal.read_bytes()).hexdigest()
    inputs, compile_cost = timed(lambda: load_manual_profile(args.bundle, args.proposal))
    print(json.dumps(profile_scope(inputs)), flush=True)
    details, timings, metrics, _ = execute(inputs, args.out)
    artifacts = artifact_inventory(args.out / "export")
    if before != source_state(BACKEND) or git_revision != revision():
        raise ValueError("source changed during worker")
    if proposal_hash != hashlib.sha256(args.proposal.read_bytes()).hexdigest():
        raise ValueError("proposal changed during worker")
    return {
        **details,
        **before,
        "git_revision": git_revision,
        "pid": os.getpid(),
        "proposal_sha256": proposal_hash,
        "scope": profile_scope(inputs),
        "artifacts": artifacts,
        "artifacts_sha256": digest(artifacts),
        "raw_export_bytes": sum(row["bytes"] for row in artifacts.values()),
        "metrics": metrics,
        "timings": {
            **timings,
            "compile": compile_cost,
            "whole_child": {
                "wall_s_since_measure_entry": perf_counter() - wall,
                "cpu_s_since_process_launch": process_time(),
            },
        },
        "peak_rss_bytes_whole_process_including_compile_export": peak_rss_bytes(),
    }


def spawn(args: argparse.Namespace, out: Path, index: int) -> Json:
    directory = out / f"repeat-{index:03}"
    directory.mkdir()
    command = [
        sys.executable,
        str(SCRIPT),
        "--worker",
        "--bundle",
        str(args.bundle.resolve()),
        "--proposal",
        str(args.proposal.resolve()),
        "--out",
        str(directory),
    ]
    wall = perf_counter()
    child = subprocess.run(
        command,
        cwd=BACKEND,
        env={**os.environ, "PYTHONHASHSEED": str(index)},
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = perf_counter() - wall
    report = directory / "measurement.json"
    if child.returncode or not report.is_file():
        raise RuntimeError(
            f"worker {index} failed ({child.returncode}): "
            f"{child.stderr or child.stdout or 'missing measurement artifact'}"
        )
    result: Json = json.loads(report.read_bytes())
    actual = artifact_inventory(directory / "export")
    if actual != result["artifacts"] or digest(actual) != result["artifacts_sha256"]:
        raise ValueError("worker artifact inventory mismatch")
    result["whole_child_wall_s_including_startup_shutdown"] = elapsed
    print(json.dumps({"repeat": index, "scope": result["scope"]}), flush=True)
    return result


def verify_results(runs: list[Json], expected: Json, git_revision: str) -> dict[str, bool]:
    checks = determinism(runs)
    checks["parent_source_binding"] = all(
        run["source_sha256"] == expected["source_sha256"] and run["git_revision"] == git_revision
        for run in runs
    )
    checks["fresh_processes"] = len({run["pid"] for run in runs}) == len(runs)
    if not all(checks.values()):
        raise ValueError(f"determinism/binding mismatch: {checks}")
    return checks


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    try:
        out = prepare_output(args.out)
        if args.worker:
            exclusive_json(out / "measurement.json", measure(args))
            return 0
        expected, git_revision = source_state(BACKEND), revision()
        runs = [spawn(args, out, i) for i in range(1, args.iterations + 1)]
        checks = verify_results(runs, expected, git_revision)
        if expected != source_state(BACKEND) or git_revision != revision():
            raise ValueError("source changed during benchmark")
        result = {
            "status": "passed",
            "scope": runs[0]["scope"],
            "runs": runs,
            "deterministic": checks,
            "runtime": {
                "python": platform.python_version(),
                "platform": platform.system(),
                "machine": platform.machine(),
            },
        }
        exclusive_json(out / "benchmark.json", result)
        exclusive_json(
            out / "manifest.json",
            {
                "status": "passed",
                "report": "benchmark.json",
                "sha256": digest(result),
            },
        )
        exclusive_json(out / "latest.json", {"manifest": "manifest.json"})
        return 0
    except Exception as exc:
        print(f"benchmark failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
