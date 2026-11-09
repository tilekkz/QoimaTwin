"""Persist the frozen manual inputs before executing or exporting a V3 run."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.execution import ManualEngine
from app.v3.manual_metrics import summary
from app.v3.materialize_manifest import materialized_bytes
from app.v3.profile import CompiledManualInputs, load_manual_profile


def _write(path: Path, raw: bytes) -> dict[str, Any]:
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def persist_inputs(inputs: CompiledManualInputs, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    files = [
        _write(out / "materialized.json", materialized_bytes(inputs)),
        _write(out / "graph.json", inputs.graph_document.canonical_bytes),
    ]
    _write(
        out / "manifest.json", canonical_bytes({"input_hash": inputs.input_hash, "files": files})
    )


def materialize_manual(bundle_path: Path, profile_path: Path, out: Path) -> dict[str, Any]:
    inputs = load_manual_profile(bundle_path, profile_path)
    persist_inputs(inputs, out)
    return {
        "status": "passed",
        "input_hash": inputs.input_hash,
        "jobs": len(inputs.profile.jobs),
        "data_kind": "materialized_manual_proposal",
        "full_v3_warehouse": False,
    }


def simulate_manual(bundle_path: Path, profile_path: Path, out: Path) -> dict[str, Any]:
    from app.v3.run_export import build_manual_run
    from app.v3.run_transport import write_manual_run

    inputs = load_manual_profile(bundle_path, profile_path)
    persist_inputs(inputs, out / "inputs")
    outcome = ManualEngine(inputs.profile, inputs.graph, check_invariants=True).run(
        inputs.horizon_tick, inputs.end_tick
    )
    run = build_manual_run(
        inputs.profile,
        inputs.graph,
        outcome,
        graph_document=inputs.graph_document.decode(),
        end_tick_limit=inputs.end_tick,
    )
    write_manual_run(run, out / "run")
    _write(out / "metrics.json", canonical_bytes(summary(inputs.profile, outcome)))
    return {
        "status": outcome.at_end.status,
        "run_id": run["run_id"],
        "input_hash": inputs.input_hash,
        "source_label": "actual_engine_run",
        "full_v3_warehouse": False,
        "manifest": "run/manifest.json",
    }
