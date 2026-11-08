"""Immutable connected trace publication and exact captured-checkpoint retrieval only."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.flow_run import validate_flow_run
from app.v3.flow_run_schema import MAX_CHUNK_BYTES, validate_schema
from app.v3.flow_transport_inputs import validate_input_binding
from app.v3.flow_transport_schema import validate_manifest
from app.v3.run_publication import chunks, publish


def write_flow_run(
    run: dict[str, Any], out: Path, *, inputs: bytes, max_chunk_bytes: int = MAX_CHUNK_BYTES
) -> dict[str, Any]:
    validate_flow_run(run)
    validate_input_binding(run, inputs)
    if sha256(inputs).hexdigest() != run["input_hash"]:
        raise ValueError("Raw frozen input hash differs from run")
    if type(max_chunk_bytes) is not int or not 12 < max_chunk_bytes <= MAX_CHUNK_BYTES:
        raise ValueError("Invalid connected flow raw chunk size")
    descriptor = _inputs(out, inputs)
    metadata = {k: v for k, v in run.items() if k not in {"catalog", "events", "checkpoints"}}
    manifest = {
        "schema_id": "qoima.connected-small-manifest.v3-proposal",
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "horizon_tick": run["horizon_tick"],
        "observed_until_tick": run["observed_until_tick"],
        "chunk_ticks": 60_000_000,
        "max_chunk_bytes": max_chunk_bytes,
        "inputs": descriptor,
        "catalog": publish(out, "catalog.json", canonical_bytes(run["catalog"])),
        "metadata": publish(out, "metadata.json", canonical_bytes(metadata)),
        "event_chunks": chunks(out, "events", run["events"], 60_000_000, max_chunk_bytes),
        "checkpoint_chunks": chunks(
            out, "checkpoints", run["checkpoints"], 60_000_000, max_chunk_bytes
        ),
    }
    validate_manifest(manifest)
    publish(out, "manifest.json", canonical_bytes(manifest))
    return manifest


def _inputs(out: Path, raw: bytes) -> dict[str, Any]:
    if out.exists() and (not out.is_dir() or any(p.name != "inputs.json" for p in out.iterdir())):
        raise ValueError("Output must be empty or contain only exact prewritten inputs")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "inputs.json"
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError("Prewritten inputs differ from compiled evidence")
        return {"path": "inputs.json", "bytes": len(raw), "sha256": sha256(raw).hexdigest()}
    return publish(out, "inputs.json", raw)


def _load(root: Path, descriptor: dict[str, Any], maximum: int | None = None) -> bytes:
    relative: str = descriptor["path"]
    path = (root / relative).resolve()
    if path == root.resolve() or not path.is_relative_to(root.resolve()):
        raise ValueError("Flow artifact path escapes its directory")
    if maximum is not None and descriptor["bytes"] > maximum:
        raise ValueError("Flow chunk exceeds raw byte bound")
    if path.stat().st_size != descriptor["bytes"]:
        raise ValueError("Flow raw artifact byte size mismatch")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != descriptor["sha256"]:
        raise ValueError("Flow raw artifact hash mismatch")
    return raw


def _object(raw: bytes) -> dict[str, Any]:
    value = parse_json(raw)
    if not isinstance(value, dict):
        raise ValueError("Flow artifact requires JSON object")
    return value


def read_flow_run(root: Path) -> dict[str, Any]:
    manifest = _object((root / "manifest.json").read_bytes())
    validate_manifest(manifest)
    run = _object(_load(root, manifest["metadata"]))
    validate_schema(run, "metadata")
    if any(
        run[k] != manifest[k]
        for k in ("run_id", "input_hash", "horizon_tick", "observed_until_tick")
    ):
        raise ValueError("Flow manifest/metadata identity differs")
    run["catalog"] = _object(_load(root, manifest["catalog"]))
    for key, target in (("event_chunks", "events"), ("checkpoint_chunks", "checkpoints")):
        run[target] = [
            row
            for descriptor in manifest[key]
            for row in _items(root, descriptor, manifest["max_chunk_bytes"], target)
        ]
    validate_flow_run(run)
    validate_input_binding(run, _load(root, manifest["inputs"]))
    return run


def _items(root: Path, descriptor: dict[str, Any], maximum: int, kind: str) -> list[dict[str, Any]]:
    value = _object(_load(root, descriptor, maximum))
    validate_schema(value, kind)
    rows: list[dict[str, Any]] = value["items"]
    ticks = [r["tick"] for r in rows]
    if not ticks or ticks != sorted(ticks):
        raise ValueError("Flow chunk items must be ordered")
    if ticks[0] != descriptor["first_tick"] or ticks[-1] != descriptor["last_tick"]:
        raise ValueError("Flow chunk content range differs from manifest")
    return rows


def captured_checkpoint(root: Path, tick: int) -> dict[str, Any]:
    if type(tick) is not int or tick < 0:
        raise ValueError("Exact captured checkpoint tick required")
    run = read_flow_run(root)
    for checkpoint in run["checkpoints"]:
        if checkpoint["tick"] == tick:
            return checkpoint  # type: ignore[no-any-return]
    raise ValueError("Tick is not an actual captured checkpoint; arbitrary seek is unsupported")


def event_window(root: Path, start_tick: int, end_tick: int) -> list[dict[str, Any]]:
    if type(start_tick) is not int or type(end_tick) is not int or not 0 <= start_tick < end_tick:
        raise ValueError("Require a nonnegative half-open event window")
    if end_tick - start_tick > 60_000_000:
        raise ValueError("Event window may span at most 60 seconds")
    return [e for e in read_flow_run(root)["events"] if start_tick <= e["tick"] < end_tick]
