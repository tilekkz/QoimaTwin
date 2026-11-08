"""Raw-hashed whole publication; captured state retrieval never promises arbitrary replay."""

from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_run_schema import MAX_CHUNK_BYTES
from app.v3.interface import Json
from app.v3.receipt_run_journal import same
from app.v3.receipt_transport import _inputs, _load, _object
from app.v3.run_publication import chunks, publish
from app.v3.whole_run import validate_whole_run
from app.v3.whole_run_schema import validate_schema
from app.v3.whole_transport_inputs import validate_input_binding
from app.v3.whole_transport_schema import MANIFEST_ID, validate_manifest


def write_whole_run(
    run: Json, out: Path, *, inputs: bytes, max_chunk_bytes: int = MAX_CHUNK_BYTES
) -> Json:
    validate_input_binding(run, inputs)
    validate_whole_run(run)
    if type(max_chunk_bytes) is not int or not 12 < max_chunk_bytes <= MAX_CHUNK_BYTES:
        raise ValueError("Invalid whole raw chunk byte limit")
    descriptor = _inputs(out, inputs)
    metadata = {k: v for k, v in run.items() if k not in {"catalog", "events", "checkpoints"}}
    manifest = {
        "schema_id": MANIFEST_ID,
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        **{
            k: run[k]
            for k in (
                "run_id",
                "input_hash",
                "physical_input_hash",
                "horizon_tick",
                "observed_until_tick",
            )
        },
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


def read_whole_run(root: Path) -> Json:
    manifest = _object((root / "manifest.json").read_bytes())
    validate_manifest(manifest)
    run = _object(_load(root, manifest["metadata"]))
    validate_schema(run, "metadata")
    keys = ("run_id", "input_hash", "physical_input_hash", "horizon_tick", "observed_until_tick")
    same(
        {k: run[k] for k in keys}, {k: manifest[k] for k in keys}, "Whole manifest/metadata differs"
    )
    run["catalog"] = _object(_load(root, manifest["catalog"]))
    for source, target in (("event_chunks", "events"), ("checkpoint_chunks", "checkpoints")):
        run[target] = [
            row
            for item in manifest[source]
            for row in _items(root, item, manifest["max_chunk_bytes"], target)
        ]
    validate_input_binding(run, _load(root, manifest["inputs"]))
    validate_whole_run(run)
    return run


def _items(root: Path, descriptor: Json, maximum: int, kind: str) -> list[Json]:
    value = _object(_load(root, descriptor, maximum))
    validate_schema(value, kind)
    rows: list[Json] = value["items"]
    ticks = [row["tick"] for row in rows]
    if not ticks or ticks != sorted(ticks):
        raise ValueError("Whole chunk items must be nonempty and ordered")
    if ticks[0] != descriptor["first_tick"] or ticks[-1] != descriptor["last_tick"]:
        raise ValueError("Whole chunk actual range differs from manifest")
    if not descriptor["start_tick"] <= ticks[0] <= ticks[-1] < descriptor["end_tick"]:
        raise ValueError("Whole chunk violates its half-open bucket")
    return rows


def captured_checkpoint(root: Path, tick: int) -> Json:
    if type(tick) is not int or tick < 0:
        raise ValueError("Exact captured checkpoint tick required")
    for point in read_whole_run(root)["checkpoints"]:
        if point["tick"] == tick:
            return dict(point)
    raise ValueError("Tick is not an actual captured checkpoint; arbitrary seek is unsupported")


def event_window(root: Path, start_tick: int, end_tick: int) -> list[Json]:
    if any(type(t) is not int for t in (start_tick, end_tick)) or not 0 <= start_tick < end_tick:
        raise ValueError("Whole event window requires nonnegative exact half-open bounds")
    if end_tick - start_tick > 60_000_000:
        raise ValueError("Whole event window may span at most 60 seconds")
    return [e for e in read_whole_run(root)["events"] if start_tick <= e["tick"] < end_tick]
