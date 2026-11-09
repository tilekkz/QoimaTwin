"""Manifest-last N1 bundles preserve native observations and revalidate their semantics."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_transport import _events, _read_events, _read_snapshots, _snapshots
from app.v3.coordinator_transport_files import (
    closed_inventory,
    publish,
    put,
    read_file,
    read_json,
    require_output,
)
from app.v3.relocation_run import validate_relocation_run
from app.v3.relocation_run_schema import PUBLICATION_VERSION, RUN_FIELDS, TRANSPORT_VERSION
from app.v3.relocation_transport_schema import validate_manifest

IDENTITY_FIELDS = (
    "engine_version",
    "run_id",
    "input_hash",
    "common_input_hash",
    "registry_common_hash",
)
OUTCOME_METADATA = frozenset(
    {
        "status",
        "business_complete_tick",
        "resource_drained_tick",
        "observation_end_tick",
        "staffing_status",
        "constraint_violations",
    }
)


def write_relocation_run(run: dict[str, Any], out_dir: Path, *, inputs: bytes) -> dict[str, Any]:
    require_output(out_dir, inputs)
    validate_relocation_run(run, inputs=inputs)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".relocation-stage-", dir=out_dir.parent) as temporary:
        stage = Path(temporary)
        manifest = _stage(stage, run, inputs)
        publish(stage, out_dir, inputs)
    return manifest


def _stage(stage: Path, run: dict[str, Any], inputs: bytes) -> dict[str, Any]:
    outcome = run["outcome"]
    catalog = {key: value for key, value in run.items() if key != "outcome"}
    omitted = {"events", "checkpoints", "at_horizon", "at_end"}
    catalog["outcome"] = {key: value for key, value in outcome.items() if key not in omitted}
    manifest = {
        "transport_version": TRANSPORT_VERSION,
        "schema_version": PUBLICATION_VERSION,
        **{key: run[key] for key in IDENTITY_FIELDS},
        "inputs": put(stage, "inputs.json", inputs),
        "catalog": put(stage, "catalog.json", canonical_bytes(catalog)),
        "event_chunks": _events(stage, outcome["events"]),
        "snapshot_chunks": _snapshots(stage, outcome),
    }
    validate_manifest(manifest)
    put(stage, "manifest.json", canonical_bytes(manifest))
    return manifest


def read_relocation_run(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "manifest.json"
    if (
        out_dir.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**21
    ):
        raise ValueError("Missing or invalid bounded relocation manifest")
    raw = path.read_bytes()
    manifest = parse_json(raw)
    if canonical_bytes(manifest) != raw:
        raise ValueError("Relocation manifest bytes are not canonical")
    refs = validate_manifest(manifest)
    closed_inventory(out_dir, refs)
    inputs = read_file(out_dir, manifest["inputs"])
    run = _catalog(read_json(out_dir, manifest["catalog"]))
    run["outcome"]["events"] = _read_events(out_dir, manifest["event_chunks"])
    _read_snapshots(out_dir, manifest["snapshot_chunks"], run["outcome"])
    if any(manifest[key] != run[key] for key in IDENTITY_FIELDS):
        raise ValueError("Relocation catalog and manifest identity differ")
    validate_relocation_run(run, inputs=inputs)
    return run


def _catalog(value: Any) -> dict[str, Any]:
    if (
        type(value) is not dict
        or value.keys() != RUN_FIELDS
        or type(value.get("outcome")) is not dict
    ):
        raise ValueError("Relocation catalog has no closed native outcome metadata")
    if value["outcome"].keys() != OUTCOME_METADATA:
        raise ValueError("Relocation catalog cannot contain mutable history or unknown metadata")
    return value
