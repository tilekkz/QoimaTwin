"""Strict source compilation and frozen evidence precede real connected engine construction."""

from pathlib import Path
from typing import Any

from app.errors import require_empty_output
from app.storage.canonical_json import parse_json
from app.v3.conveyor_source import load_conveyor_source
from app.v3.flow_profile import compile_light_profile
from app.v3.flow_run import build_flow_run
from app.v3.flow_transport import write_flow_run
from app.v3.inputs import load_v3_bundle
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.run_publication import publish


def simulate_light_file(bundle_path: Path, profile_path: Path, out: Path) -> dict[str, Any]:
    require_empty_output(out)
    document = parse_json(profile_path.read_bytes())
    bundle = load_v3_bundle(bundle_path)
    conveyor = load_conveyor_source(bundle)
    inputs = compile_light_profile(bundle, conveyor, document)
    publish(out, "inputs.json", inputs.frozen_bytes)
    outcome = LightFlowEngine(inputs.profile, conveyor).run(inputs.horizon_tick, inputs.end_tick)
    run = build_flow_run(inputs, outcome, validate=False)
    manifest = write_flow_run(run, out, inputs=inputs.frozen_bytes)
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "manifest": str(out / "manifest.json"),
        "metrics": run["metrics"],
        "capabilities": run["capabilities"],
        "event_chunks": len(manifest["event_chunks"]),
        "checkpoint_chunks": len(manifest["checkpoint_chunks"]),
    }
