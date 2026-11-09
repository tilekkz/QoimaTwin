"""Exact component trace; deliberately separate from the warehouse replay contract."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.belt_models import BeltOutcome
from app.v3.belt_profile import CompiledBeltProfile
from app.v3.run_values import record

BELT_ENGINE_VERSION = "qoima-belt-component-v3-proposal-1"


def write_file(path: Path, raw: bytes) -> dict[str, Any]:
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def publish_trace(
    inputs: CompiledBeltProfile,
    outcome: BeltOutcome,
    out: Path,
    input_file: dict[str, Any],
) -> dict[str, Any]:
    identity = {"engine_version": BELT_ENGINE_VERSION, "input_hash": inputs.input_hash}
    run_id = sha256_hex(identity)
    metadata = {
        **identity,
        "run_id": run_id,
        "status": outcome.status,
        "source_label": "actual_engine_component_run",
        "full_v3_warehouse": False,
        "inventory_integration": False,
        "frontend_adapter": False,
    }
    trace = {
        "schema": "qoima.conveyor-component-trace.v3-proposal",
        "schema_version": "0.1",
        **metadata,
        "outcome": record(outcome),
    }
    trace_file = write_file(out / "trace.json", canonical_bytes(trace))
    manifest = {**metadata, "files": [input_file, trace_file]}
    write_file(out / "manifest.json", canonical_bytes(manifest))
    return {**metadata, "manifest": "manifest.json", "events": len(outcome.events)}
