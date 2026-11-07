"""Read bounded V3 manual event/checkpoint artifacts by exact integer tick."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3.interface import Json
from app.v3.run_export import run_identity, validate_manual_run
from app.v3.run_publication import chunks, publish
from app.v3.run_replay import apply_event, settle
from app.v3.run_transport_schema import MAX_CHUNK_BYTES, validate_transport


def write_manual_run(
    run: Json,
    out_dir: Path,
    *,
    chunk_ticks: int = 60_000_000,
    max_chunk_bytes: int = 8 * 1024 * 1024,
) -> Json:
    validate_manual_run(run)
    if type(chunk_ticks) is not int or chunk_ticks <= 0:
        raise ValueError("manual chunk interval requires positive integer ticks")
    if type(max_chunk_bytes) is not int or not 12 < max_chunk_bytes <= MAX_CHUNK_BYTES:
        raise ValueError("manual raw chunk byte limit is too small")
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
        raise ValueError("manual output directory must be empty")
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        key: value
        for key, value in run.items()
        if key not in {"graph_document", "events", "snapshots"}
    }
    manifest = {
        "schema_id": "qoima.manual-manifest.v3-proposal",
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        "run_id": run["run_id"],
        "clock": run["clock"],
        "observed_until_tick": run["observed_until_tick"],
        "max_chunk_bytes": max_chunk_bytes,
        "chunk_ticks": chunk_ticks,
        "metadata": publish(out_dir, "metadata.json", canonical_bytes(metadata)),
        "graph_document": publish(out_dir, "graph.json", canonical_bytes(run["graph_document"])),
        "event_chunks": chunks(out_dir, "events", run["events"], chunk_ticks, max_chunk_bytes),
        "snapshot_chunks": chunks(
            out_dir, "snapshots", run["snapshots"], chunk_ticks, max_chunk_bytes
        ),
    }
    validate_transport(manifest, "manifest")
    publish(out_dir, "manifest.json", canonical_bytes(manifest))
    return manifest


def _object(raw: bytes) -> Json:
    value = parse_json(raw)
    if not isinstance(value, dict):
        raise ValueError("manual transport requires JSON objects")
    return value


def _load(root: Path, descriptor: Json, maximum: int | None = None) -> Json:
    path = (root / descriptor["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("manual descriptor path escapes its artifact directory")
    if maximum is not None and descriptor["bytes"] > maximum:
        raise ValueError("manual descriptor exceeds raw chunk byte limit")
    if path.stat().st_size != descriptor["bytes"]:
        raise ValueError("manual artifact raw byte size mismatch")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != descriptor["sha256"]:
        raise ValueError("manual artifact raw byte hash mismatch")
    return _object(raw)


def _open(root: Path) -> tuple[Json, Json]:
    manifest = _object((root / "manifest.json").read_bytes())
    validate_transport(manifest, "manifest")
    metadata = _load(root, manifest["metadata"])
    validate_transport(metadata, "metadata")
    if metadata["run_id"] != manifest["run_id"] or metadata["run_id"] != run_identity(metadata):
        raise ValueError("manual manifest run identity mismatch")
    if metadata["profile"]["graph_sha256"] != manifest["graph_document"]["sha256"]:
        raise ValueError("manual manifest graph binding mismatch")
    if any(metadata[key] != manifest[key] for key in ("clock", "observed_until_tick")):
        raise ValueError("manual manifest metadata boundary/clock mismatch")
    return manifest, metadata


def _items(root: Path, descriptor: Json, maximum: int, kind: str) -> list[Json]:
    value = _load(root, descriptor, maximum)
    validate_transport(value, kind)
    rows: list[Json] = value["items"]
    ticks = [row["tick"] for row in rows]
    if not ticks or ticks != sorted(ticks):
        raise ValueError("manual chunk must contain ordered timeline items")
    if ticks[0] != descriptor["first_tick"] or ticks[-1] != descriptor["last_tick"]:
        raise ValueError("manual chunk content differs from its declared time range")
    return rows


def read_manual_run(root: Path) -> Json:
    manifest, value = _open(root)
    value["graph_document"] = _load(root, manifest["graph_document"])
    for key, output in (("event_chunks", "events"), ("snapshot_chunks", "snapshots")):
        value[output] = [
            row
            for descriptor in manifest[key]
            for row in _items(root, descriptor, manifest["max_chunk_bytes"], output)
        ]
    validate_manual_run(value)
    return value


def seek_manual_run(root: Path, cutoff_tick: int) -> Json:
    manifest, metadata = _open(root)
    if type(cutoff_tick) is not int or not 0 <= cutoff_tick <= metadata["observed_until_tick"]:
        raise ValueError("manual seek cutoff is outside the observed timeline")
    candidates = [row for row in manifest["snapshot_chunks"] if row["first_tick"] <= cutoff_tick]
    descriptor = max(candidates, key=lambda row: row["first_tick"])
    rows = _items(root, descriptor, manifest["max_chunk_bytes"], "snapshots")
    checkpoint = max(
        (row for row in rows if row["tick"] <= cutoff_tick), key=lambda row: row["tick"]
    )
    if sha256_hex(checkpoint["state"]) != checkpoint["state_hash"]:
        raise ValueError("manual checkpoint state hash mismatch")
    state: Json = deepcopy(checkpoint["state"])
    for descriptor in manifest["event_chunks"]:
        if descriptor["last_tick"] < checkpoint["tick"] or descriptor["first_tick"] > cutoff_tick:
            continue
        events = _items(root, descriptor, manifest["max_chunk_bytes"], "events")
        for event in events:
            if event["seq"] > checkpoint["through_seq"] and event["tick"] <= cutoff_tick:
                apply_event(state, event)
    settle(state, metadata["profile"], cutoff_tick)
    return state
