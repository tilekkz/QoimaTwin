"""Measure reproducible runs from backend/: python tools/benchmark_runs.py --out OUTPUT.

Each iteration is a fresh process. Timing and memory are observations, never test oracles.
Output must be new and outside the repository. Inputs are persisted before each engine run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from time import perf_counter, process_time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.contracts.loader import ContractBundle
    from app.data.scenario_materializer import Profile
    from app.simulation.context import RunInputs
    from app.simulation.engine import Engine, RunOutcome

type Json = dict[str, Any]
PROFILES = {"large-normal": 240, "large-peak": 600}
BACKEND = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: object) -> None:
    from app.storage.canonical_json import canonical_bytes

    path.write_bytes(canonical_bytes(value))


def _source_state() -> Json:
    from app.storage.canonical_json import sha256_hex

    files = {
        path.relative_to(BACKEND).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((BACKEND / "app").rglob("*.py"))
    }
    files["tools/benchmark_runs.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "source_sha256": sha256_hex(files),
        "source_file_count": len(files),
        "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _runtime() -> Json:
    from app.storage.canonical_json import sha256_hex
    from app.version import ENGINE_VERSION

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
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


def _inputs(bundle: ContractBundle, profile: Profile, horizon_s: int, out: Path) -> RunInputs:
    from app.contracts.assignment import Assignment
    from app.contracts.scenario import Scenario
    from app.data.scenario_materializer import materialize
    from app.simulation.context import RunInputs

    scenario = materialize(profile, horizon_s, bundle.config).scenario
    directory = out / "inputs"
    directory.mkdir()
    path = directory / "scenario.json"
    _write_json(path, scenario.model_dump(mode="json"))
    scenario = Scenario.from_json_text(path.read_bytes())
    assignment = Assignment.from_json_text(
        (bundle.directory / "assignment.example.json").read_bytes()
    )
    return RunInputs(bundle.layout, bundle.config, bundle.actors, assignment, scenario)


def _metadata(engine: Engine, outcome: RunOutcome, summary: Json) -> Json:
    from app.exporter.identity import fingerprint

    return {
        "identity": fingerprint(engine.ctx.inputs),
        "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
        "metrics": summary,
        "provenance": engine.ctx.inputs.scenario.provenance.model_dump(mode="json"),
        "ticks_per_second": engine.ctx.grid.ticks_per_second,
    }


def _export(
    engine: Engine, outcome: RunOutcome, out: Path, format_name: str
) -> tuple[Json, Json, Json]:
    from app.exporter.run import export_run, write_run
    from app.simulation.metrics_summary import summary as metrics_summary

    summary = metrics_summary(engine, outcome)
    metadata = _metadata(engine, outcome, summary)
    options: Json = {
        "metadata": metadata,
        "chunk_duration_s": engine.ctx.config.chunk_duration_s,
        "snapshot_interval_s": engine.ctx.config.snapshot_interval_s,
        "allow_existing_inputs": True,
    }
    if format_name == "proposal":
        proposal = importlib.import_module("app.exporter.proposal")
        run = proposal.export_proposal(engine, outcome, validate=False)
        manifest = proposal.write_proposal_run(run, out, **options)
    else:
        run = export_run(engine, outcome, validate=False)
        manifest = write_run(run, out, **options)
    return run, manifest, summary


def _event_chunks(manifest: Json) -> list[Json]:
    key = "chunks" if "chunks" in manifest else "event_chunks"
    chunks: list[Json] = manifest[key]
    return chunks


def _sizes(out: Path, manifest: Json) -> dict[str, int]:
    events = _event_chunks(manifest)
    snapshots = manifest.get("snapshot_chunks", [])
    event_bytes = sum((out / entry["path"]).stat().st_size for entry in events)
    snapshot_bytes = sum((out / entry["path"]).stat().st_size for entry in snapshots)
    catalog = (out / manifest["catalog"]["path"]).stat().st_size
    inline = out / "run.json"
    return {
        "inline_bytes": inline.stat().st_size if inline.exists() else 0,
        "events_chunks_bytes": event_bytes,
        "snapshots_chunks_bytes": snapshot_bytes,
        "chunks_only_bytes": event_bytes + snapshot_bytes,
        "chunk_bundle_bytes": event_bytes
        + snapshot_bytes
        + catalog
        + (out / "manifest.json").stat().st_size,
        "all_files_bytes": sum(path.stat().st_size for path in out.rglob("*") if path.is_file()),
    }


def _timed[T](action: Callable[[], T]) -> tuple[T, dict[str, float]]:
    wall, cpu = perf_counter(), process_time()
    value = action()
    return value, {"wall_s": perf_counter() - wall, "cpu_s": process_time() - cpu}


def _windows_peak_rss() -> int:
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PeakWorkingSetSize)


def _peak_rss_bytes() -> int:
    if os.name == "nt":
        return _windows_peak_rss()
    resource = importlib.import_module("resource")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _expected_orders(profile: str, horizon_s: int) -> int:
    # Arrivals are (i + 0.5) * 3600 / rate, and only arrivals strictly before H enter.
    return max(0, math.ceil(Fraction(PROFILES[profile] * horizon_s, 3600) - Fraction(1, 2)))


def _journal_hash(engine: Engine) -> str:
    from app.storage.canonical_json import canonical_bytes

    digest = hashlib.sha256(b"[")
    for index, event in enumerate(engine.ctx.recorder.events):
        if index:
            digest.update(b",")
        digest.update(
            canonical_bytes(
                {
                    "seq": event.seq,
                    "at_tick": event.at_tick,
                    "phase": int(event.phase),
                    "kind": event.kind,
                    "entity_id": event.entity_id,
                    "payload": event.payload,
                }
            )
        )
    digest.update(b"]")
    return digest.hexdigest()


def _measurement_details(
    engine: Engine, outcome: RunOutcome, run: Json, manifest: Json, summary: Json
) -> Json:
    from app.storage.canonical_json import sha256_hex

    return {
        "run_id": run["run_id"],
        "events_sha256": sha256_hex(run["events"]),
        "journal_sha256": _journal_hash(engine),
        "scenario_sha256": sha256_hex(engine.ctx.inputs.scenario.model_dump(mode="json")),
        "status": outcome.status.value,
        "termination_reason": outcome.termination.value,
        "termination_reasons": summary.get("termination_reasons", [outcome.termination.value]),
        "subsystems": summary.get("subsystems", {}),
        "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
        "snapshot_count": len(run["snapshots"]),
        "event_count": len(run["events"]),
        "action_count": len(run["actions"]),
        "chunk_count": len(_event_chunks(manifest)) + len(manifest.get("snapshot_chunks", [])),
        "event_chunk_count": len(_event_chunks(manifest)),
        "snapshot_chunk_count": len(manifest.get("snapshot_chunks", [])),
        "metrics": summary,
    }


def _measure(bundle: ContractBundle, args: argparse.Namespace, profile: Profile, out: Path) -> Json:
    from app.simulation.engine import Engine

    out.mkdir(parents=True, exist_ok=False)
    runtime = _runtime()
    total_wall, total_cpu = perf_counter(), process_time()
    inputs, materialization = _timed(lambda: _inputs(bundle, profile, args.horizon_s, out))
    engine, construction = _timed(lambda: Engine(inputs, check_invariants=True))
    outcome, simulation = _timed(engine.run)
    (run, manifest, summary), export = _timed(lambda: _export(engine, outcome, out, args.format))
    details = _measurement_details(engine, outcome, run, manifest, summary)
    expected = _expected_orders(profile, args.horizon_s)
    checks = {
        "offered_count": len(inputs.scenario.orders) == expected,
        "arrived_count": engine.metrics.counts()["arrived_total"] == expected,
        "invariants": not engine.ctx.ledger.check_conservation(),
        "run_not_failed": outcome.status.value != "failed",
        "source_unchanged": runtime["source_sha256"] == _source_state()["source_sha256"],
    }
    return {
        "path": str(out),
        "pid": os.getpid(),
        "format": args.format,
        "runtime": runtime,
        "source_sha256": runtime["source_sha256"],
        **details,
        "timings": {
            "materialization": materialization,
            "construction": construction,
            "engine": simulation,
            "export_including_metrics_validation_and_io": export,
            "total": {"wall_s": perf_counter() - total_wall, "cpu_s": process_time() - total_cpu},
        },
        "peak_rss_bytes": _peak_rss_bytes(),
        "sizes": _sizes(out, manifest),
        "checks": checks,
    }


def _determinism(measurements: list[Json]) -> dict[str, bool | None]:
    keys = (
        "run_id",
        "events_sha256",
        "scenario_sha256",
        "metrics",
        "journal_sha256",
        "source_sha256",
    )
    return {
        key: all(item.get(key) == measurements[0].get(key) for item in measurements[1:])
        if len(measurements) >= 2
        else None
        for key in keys
    }


def _spawn_measurement(args: argparse.Namespace, profile: str, directory: Path, index: int) -> Json:
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / f"measurement-{index}.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--out",
        str(directory / f"run-{index}"),
        "--worker-report",
        str(report),
        "--profiles",
        profile,
        "--horizon-s",
        str(args.horizon_s),
        "--format",
        args.format,
    ]
    child = subprocess.run(
        command,
        cwd=BACKEND,
        env={**os.environ, "PYTHONHASHSEED": str(index)},
        capture_output=True,
        text=True,
        check=False,
    )
    if child.returncode or not report.exists():
        raise RuntimeError(f"worker {profile}/{index} failed: {child.stderr or child.stdout}")
    result: Json = json.loads(report.read_text(encoding="utf-8"))
    return result


def _profile(args: argparse.Namespace, profile: str, out: Path) -> Json:
    measurements: list[Json] = []
    for index in range(1, args.iterations + 1):
        print(f"{profile}: run {index}/{args.iterations}", flush=True)
        measurements.append(_spawn_measurement(args, profile, out / profile, index))
    deterministic = _determinism(measurements)
    return {
        "offered_orders_expected_from_spec": _expected_orders(profile, args.horizon_s),
        "deterministic": deterministic,
        "determinism_checked": len(measurements) >= 2,
        "passed": all(value is not False for value in deterministic.values())
        and all(all(run["checks"].values()) for run in measurements),
        "runs": measurements,
    }


def _output(path: Path) -> Path:
    out = path.expanduser().resolve()
    repository = BACKEND.parent
    if out == repository or repository in out.parents:
        raise ValueError("benchmark output must be outside the repository")
    out.mkdir(parents=True, exist_ok=False)
    return out


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _horizon(value: str) -> int:
    number = _positive(value)
    if number > 168 * 3600:
        raise argparse.ArgumentTypeError("horizon must not exceed 168 hours")
    return number


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--horizon-s", type=_horizon, default=3600)
    parser.add_argument("--iterations", type=_positive, default=2)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--format", choices=("v2", "proposal"), default="v2")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-report", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _worker(args: argparse.Namespace) -> int:
    from app.contracts.loader import load_contract_bundle
    from app.settings import default_contracts_dir

    if args.worker_report is None or len(args.profiles) != 1:
        raise ValueError("worker requires exactly one profile and a report path")
    bundle = load_contract_bundle(default_contracts_dir())
    result = _measure(bundle, args, args.profiles[0], args.out)
    _write_json(args.worker_report, result)
    return 0


def _report(args: argparse.Namespace) -> Json:
    return {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "runtime": _runtime(),
        "horizon_s": args.horizon_s,
        "iterations": args.iterations,
        "format": args.format,
        "profiles": {},
        "status": "running",
        "memory_semantics": "Peak resident bytes of a fresh worker, including imports and export",
        "size_semantics": {
            "inline_bytes": "raw run.json only; zero when not written",
            "chunk_bundle_bytes": "manifest + catalog + referenced chunks; no inline or inputs",
            "all_files_bytes": "all files in run directory, including persisted inputs",
        },
        "partial_semantics": "A deterministic partial run may pass; inspect status and subsystems",
    }


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    if args.worker:
        return _worker(args)
    out = _output(args.out)
    report = _report(args)
    try:
        for profile in args.profiles:
            report["profiles"][profile] = _profile(args, profile, out)
            _write_json(out / "benchmark.json", report)
        report["status"] = (
            "passed" if all(p["passed"] for p in report["profiles"].values()) else "failed"
        )
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    _write_json(out / "benchmark.json", report)
    print(json.dumps({"status": report["status"], "report": str(out / "benchmark.json")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))
    raise SystemExit(main())
