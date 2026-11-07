"""The immutable inline-v2 projection and a hashed chunk transport envelope."""

import hashlib
import math
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.data.scenario_materializer import _atomic_write
from app.errors import require_empty_output
from app.exporter.actions import project_actions
from app.exporter.catalog import cargo_catalog, initial_state
from app.exporter.events import project_events
from app.exporter.identity import fingerprint
from app.exporter.metrics import project_metrics
from app.exporter.validation import validate_run
from app.simulation.chunks import split_events
from app.simulation.engine import Engine, RunOutcome
from app.simulation.recorder import Event
from app.simulation.scheduler import Phase
from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.version import ENGINE_VERSION

V2_HASHES = ("orders", "receipts", "config", "initial_inventory", "assignment")


def export_run(engine: Engine, outcome: RunOutcome, *, validate: bool = True) -> dict[str, Any]:
    inputs = engine.ctx.inputs
    identity = fingerprint(inputs)
    events = project_events(engine)
    actions = project_actions(engine, outcome.end_tick)
    result = {
        "schema_version": "2.0",
        "run_id": sha256_hex(identity),
        "layout_version": inputs.layout.layout_version,
        "engine_version": ENGINE_VERSION,
        "scenario_id": inputs.scenario.scenario_id,
        "experiment_type": inputs.experiment_type,
        "input_hashes": {key: identity["hashes"][key] for key in V2_HASHES},
        "status": str(outcome.status),
        "termination_reason": str(outcome.termination),
        "horizon_s": inputs.scenario.horizon_s,
        "actors": [
            a.model_dump(mode="json", exclude_none=True)
            for a in sorted(inputs.actors.actors, key=lambda a: a.actor_id)
        ],
        "cargo": cargo_catalog(engine),
        "initial_state": initial_state(engine),
        "actions": actions,
        "events": events,
        "snapshots": _snapshots(engine, events, actions),
        "metrics": project_metrics(engine, outcome),
    }
    if validate:
        validate_run(result)
    return result


def _snapshots(
    engine: Engine, events: list[dict[str, Any]], actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    times = [event["at_s"] for event in events]
    by_id = {action["action_id"]: action for action in actions}
    result = []
    for snapshot in engine.checkpoints.snapshots:
        seconds = snapshot.at_tick / engine.ctx.grid.ticks_per_second
        state = snapshot.state
        _project_snapshot_actions(state, by_id, engine.ctx.grid.ticks_per_second)
        state["checkpoint"] = {
            "at_tick": snapshot.at_tick,
            "last_seq": bisect_right(times, seconds) - 1,
            "state_hash": sha256_hex(state),
        }
        result.append({"at_s": seconds, "state": state})
    return result


def _project_snapshot_actions(
    state: dict[str, Any], actions: dict[str, dict[str, Any]], tps: int
) -> None:
    for actor in state["actors"]:
        action = actor["action"]
        if action is None:
            continue
        projected = actions.get(action["action_id"])
        if projected is None:
            # A service/drive scheduled exactly at the cutoff has performed no interval.
            actor["pos"] = action["waypoints"][0][1] if action["waypoints"] else action["pos"]
            actor["action"] = None
            continue
        action["end_tick"] = round(projected["end_s"] * tps)
        if "waypoints" in projected:
            action["waypoints"] = [
                [p["node_id"], p["pos"], round(p["at_s"] * tps)] for p in projected["waypoints"]
            ]


def _publish(out_dir: Path, name: str, value: Any) -> dict[str, Any]:
    raw = canonical_bytes(value)
    path = out_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, raw)
    return {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _chunks(
    run: dict[str, Any], out_dir: Path, end_s: float, chunk_s: float, tps: int
) -> list[dict[str, Any]]:
    rows = run["events"]
    events = [
        Event(
            e["seq"],
            e["payload"].get("at_tick", round(e["at_s"] * tps)),
            Phase(e["phase"]),
            e["kind"],
            e["entity_id"],
            e["payload"],
        )
        for e in rows
    ]
    buckets = split_events(events, _interval_ticks(chunk_s, tps), round(end_s * tps))
    chunks = []
    for bucket in buckets:
        start, end = bucket.start_tick / tps, bucket.end_tick / tps
        payload = {
            "run_id": run["run_id"],
            "start_s": start,
            "end_s": end,
            "events": [rows[event.seq] for event in bucket.events],
            "actions": [a for a in run["actions"] if a["start_s"] < end and a["end_s"] > start],
            "snapshots": [s for s in run["snapshots"] if start <= s["at_s"] < end],
        }
        chunks.append(
            {
                **_publish(out_dir, f"chunks/{bucket.index:06d}.json", payload),
                "start_s": start,
                "end_s": end,
                "first_seq": bucket.first_seq,
                "last_seq": bucket.last_seq,
            }
        )
    return chunks


def write_run(
    run: dict[str, Any],
    out_dir: Path,
    *,
    metadata: dict[str, Any] | None = None,
    chunk_duration_s: float = 60,
    snapshot_interval_s: float = 30,
    allow_existing_inputs: bool = False,
) -> dict[str, Any]:
    require_empty_output(out_dir, allow_inputs=allow_existing_inputs)
    validate_run(run)
    metadata = metadata or {}
    allowed = {"identity", "provenance", "ended_at_s", "metrics", "ticks_per_second"}
    if metadata.keys() - allowed:
        raise ValueError("metadata cannot override authoritative manifest fields")
    tps = metadata.get("ticks_per_second", 3_000_000)
    if type(tps) is not int or tps <= 0:
        raise ValueError("timebase must be a positive integer")
    _interval_ticks(chunk_duration_s, tps)
    _interval_ticks(snapshot_interval_s, tps)
    end_s = _end_seconds(run, metadata)
    return _write_bundle(run, out_dir, metadata, end_s, chunk_duration_s, snapshot_interval_s, tps)


def _interval_ticks(seconds: float, tps: int) -> int:
    if isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("export intervals must be positive finite seconds")
    ticks = Fraction(str(seconds)) * tps
    if ticks.denominator != 1:
        raise ValueError("export interval is not exactly representable on the time grid")
    return ticks.numerator


def _end_seconds(run: dict[str, Any], metadata: dict[str, Any]) -> float:
    end_s = max(
        [e["at_s"] for e in run["events"]]
        + [a["end_s"] for a in run["actions"]]
        + [s["at_s"] for s in run["snapshots"]]
        + [0]
    )
    supplied_end = metadata.get("ended_at_s", end_s)
    if (
        not isinstance(supplied_end, (int, float))
        or isinstance(supplied_end, bool)
        or not math.isfinite(supplied_end)
        or supplied_end < end_s
    ):
        raise ValueError("ended_at_s precedes exported data")
    return float(supplied_end)


def _write_bundle(
    run: dict[str, Any],
    out_dir: Path,
    metadata: dict[str, Any],
    end_s: float,
    chunk_duration_s: float,
    snapshot_interval_s: float,
    tps: int,
) -> dict[str, Any]:
    inline = _publish(out_dir, "run.json", run)
    catalog = {
        key: value for key, value in run.items() if key not in {"events", "actions", "snapshots"}
    }
    catalog_ref = _publish(out_dir, "catalog.json", catalog)
    manifest = {
        "transport_version": "qoima-run-bundle-1-proposal",
        "schema_version": "2.0",
        "run_id": run["run_id"],
        "engine_version": run["engine_version"],
        "layout_version": run["layout_version"],
        "ended_at_s": end_s,
        "input_hashes": run["input_hashes"],
        "inline": inline,
        "catalog": catalog_ref,
        "chunks": _chunks(run, out_dir, end_s, chunk_duration_s, tps),
        "chunk_duration_s": chunk_duration_s,
        "snapshot_interval_s": snapshot_interval_s,
        **metadata,
    }
    _publish(out_dir, "manifest.json", manifest)
    return manifest
