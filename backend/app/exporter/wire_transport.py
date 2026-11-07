"""Atomic, manifest-last publication of the opt-in 2.1 proposal transport."""

import hashlib
import math
from collections.abc import Iterator, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.data.scenario_materializer import _atomic_write
from app.errors import require_empty_output
from app.exporter.identity import _hash
from app.exporter.wire_checkpoint_codec import encode_snapshots
from app.exporter.wire_schema import validate_proposal
from app.simulation.chunks import Chunk, split_events
from app.simulation.recorder import Event
from app.simulation.scheduler import Phase
from app.storage.canonical_json import canonical_bytes

type Json = dict[str, Any]
FULL_EVERY = 10


def _publish(out: Path, name: str, value: object) -> Json:
    raw = canonical_bytes(value)
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, raw)
    return {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _interval_ticks(seconds: float, tps: int) -> int:
    if isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("export intervals must be positive finite seconds")
    ticks = Fraction(str(seconds)) * tps
    if ticks.denominator != 1:
        raise ValueError("export interval is not exactly representable on the time grid")
    return ticks.numerator


def _metadata(run: Json, metadata: Json | None) -> Json:
    supplied = metadata or {}
    allowed = {"identity", "provenance", "ended_at_s", "metrics", "ticks_per_second"}
    if supplied.keys() - allowed:
        raise ValueError("metadata cannot override authoritative manifest fields")
    for key, value in supplied.items():
        if key == "identity":
            if not isinstance(value, dict) or any(
                run["identity"].get(name) != item for name, item in value.items()
            ):
                raise ValueError("metadata identity does not match the proposed run")
        elif key == "provenance" and (expected := run["identity"].get("provenance_sha256")):
            if not isinstance(value, dict) or _hash(value) != expected:
                raise ValueError("metadata provenance does not match the proposed run identity")
        elif key in run and run[key] != value:
            raise ValueError(f"metadata {key} does not match the proposed run")
    canonical_bytes(supplied)
    return supplied


def _end_tick(run: Json) -> int:
    tps: int = run["ticks_per_second"]
    seconds: float = run["ended_at_s"]
    if type(tps) is not int or tps <= 0:
        raise ValueError("timebase must be a positive integer")
    if isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("ended_at_s must be nonnegative finite seconds")
    latest = max(
        (
            row[field]
            for rows, field in (
                (run["events"], "at_s"),
                (run["actions"], "end_s"),
                (run["snapshots"], "at_s"),
            )
            for row in rows
        ),
        default=0,
    )
    if seconds < latest:
        raise ValueError("ended_at_s precedes exported data")
    return round(seconds * tps)


def _records(rows: list[Json]) -> list[Event]:
    return [
        Event(
            row["seq"],
            row["at_tick"],
            Phase(row["phase"]),
            row["kind"],
            row["entity_id"],
            row["payload"],
        )
        for row in rows
    ]


def _action_windows(
    chunks: Sequence[Chunk], actions: list[Json], tps: int
) -> Iterator[tuple[Chunk, list[Json]]]:
    ordered = sorted(actions, key=lambda action: (action["start_s"], action["action_id"]))
    active: list[Json] = []
    cursor = 0
    for chunk in chunks:
        start, end = chunk.start_tick / tps, chunk.end_tick / tps
        active = [action for action in active if action["end_s"] > start]
        while cursor < len(ordered) and ordered[cursor]["start_s"] < end:
            action = ordered[cursor]
            if action["end_s"] > start:
                active.append(action)
            cursor += 1
        yield chunk, sorted(active, key=lambda action: action["action_id"])


def _event_chunks(run: Json, out: Path, chunk_ticks: int, end_tick: int) -> list[Json]:
    tps, rows = run["ticks_per_second"], run["events"]
    chunks = split_events(_records(rows), chunk_ticks, end_tick)
    references = []
    for chunk, actions in _action_windows(chunks, run["actions"], tps):
        start, end = chunk.start_tick / tps, chunk.end_tick / tps
        payload = {
            "run_id": run["run_id"],
            "start_s": start,
            "end_s": end,
            "events": [rows[event.seq] for event in chunk.events],
            "actions": actions,
        }
        references.append(
            {
                **_publish(out, f"events/{chunk.index:06d}.json", payload),
                "start_s": start,
                "end_s": end,
                "first_seq": chunk.first_seq,
                "last_seq": chunk.last_seq,
            }
        )
    return references


def _snapshot_chunks(run: Json, out: Path, interval_ticks: int) -> list[Json]:
    references = []
    tps = run["ticks_per_second"]
    for index, compact in enumerate(encode_snapshots(run["snapshots"], full_every=FULL_EVERY)):
        references.append(
            {
                **_publish(out, f"snapshots/{index:06d}.json", compact),
                "start_s": compact["at_s"],
                "end_s": (compact["at_tick"] + interval_ticks) / tps,
                "at_tick": compact["at_tick"],
                "last_seq": compact["last_seq"],
                "state_hash": compact["state_hash"],
                "encoding": compact["encoding"],
                "base_at_s": compact["base_at_s"],
                "base_state_hash": compact["base_state_hash"],
                "full_base_at_s": compact["full_base_at_s"],
            }
        )
    return references


def _manifest(run: Json, metadata: Json, chunk_s: float, snapshot_s: float) -> Json:
    keys = (
        "run_id",
        "engine_version",
        "layout_version",
        "horizon_s",
        "ended_at_s",
        "ticks_per_second",
        "input_hashes",
        "identity",
        "metrics",
        "status",
        "termination_reason",
    )
    return {
        **metadata,
        **{key: run[key] for key in keys},
        "transport_version": "qoima-run-bundle-2.1-proposal",
        "schema_version": "2.1",
        "contract_status": "proposal",
        "chunk_duration_s": chunk_s,
        "snapshot_interval_s": snapshot_s,
        "snapshot_full_every": FULL_EVERY,
    }


def write_proposal_run(
    run: Json,
    out_dir: Path,
    *,
    metadata: Json | None = None,
    chunk_duration_s: float = 60,
    snapshot_interval_s: float = 30,
    allow_existing_inputs: bool = False,
    include_inline: bool = False,
) -> Json:
    """Validate once, serialize individual chunks, and expose the manifest only when complete."""
    require_empty_output(out_dir, allow_inputs=allow_existing_inputs)
    validate_proposal(run)
    supplied = _metadata(run, metadata)
    end_tick = _end_tick(run)
    tps = run["ticks_per_second"]
    chunk_ticks = _interval_ticks(chunk_duration_s, tps)
    snapshot_ticks = _interval_ticks(snapshot_interval_s, tps)
    catalog = {
        key: value for key, value in run.items() if key not in {"events", "actions", "snapshots"}
    }
    manifest = _manifest(run, supplied, chunk_duration_s, snapshot_interval_s)
    manifest["catalog"] = _publish(out_dir, "catalog.json", catalog)
    manifest["event_chunks"] = _event_chunks(run, out_dir, chunk_ticks, end_tick)
    manifest["snapshot_chunks"] = _snapshot_chunks(run, out_dir, snapshot_ticks)
    if include_inline:
        manifest["inline"] = _publish(out_dir, "run.json", run)
    _publish(out_dir, "manifest.json", manifest)
    return manifest
