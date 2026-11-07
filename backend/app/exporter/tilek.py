"""Explicit visual compatibility projection; the authoritative run stays shared v2."""

from copy import deepcopy
from pathlib import Path
from typing import Any

from app.errors import require_empty_output
from app.exporter.identity import fingerprint
from app.exporter.run import _end_seconds, _interval_ticks, _write_bundle, export_run
from app.exporter.tilek_actions import visual_actions
from app.exporter.tilek_events import bind_snapshots, visual_events
from app.exporter.tilek_validation import validate_tilek_run
from app.simulation.engine import Engine, RunOutcome
from app.storage.canonical_json import sha256_hex

WIRE_VERSION = "tilek-visual-v1"
LIMITATIONS = [
    "Visual projection only; source events, metrics and semantic states remain authoritative.",
    "Queue grids are frozen backend proposals, not approved scene coordinates.",
    "Frontend ignores terminal state and uses horizon; exact cutoff can appear IDLE.",
    "Heading, carry height, configurable belt ticks and business seek need frontend support.",
    "Real PKxx/SHIPPING cell endpoints retain Unknown cell warnings; no fake cells are created.",
    "Snapshot actor actions are source operations; source_checkpoint binds source sequence.",
]


def export_tilek_run(
    engine: Engine, outcome: RunOutcome, *, validate: bool = True
) -> dict[str, Any]:
    source = export_run(engine, outcome, validate=False)
    result = deepcopy(source)
    provenance = {
        "wire_version": WIRE_VERSION,
        "source_run_id": source["run_id"],
        "visual_projection_limitations": list(LIMITATIONS),
    }
    result["run_id"] = sha256_hex({**fingerprint(engine.ctx.inputs), "wire_version": WIRE_VERSION})
    visual_actions(engine, result["actions"])
    result["events"] = visual_events(engine, outcome.end_tick, result["events"], provenance)
    bind_snapshots(result["snapshots"], result["events"], provenance)
    if validate:
        validate_tilek_run(result)
    return result


def write_tilek_run(
    run: dict[str, Any],
    out_dir: Path,
    *,
    metadata: dict[str, Any] | None = None,
    chunk_duration_s: float = 60,
    snapshot_interval_s: float = 30,
    allow_existing_inputs: bool = False,
) -> dict[str, Any]:
    require_empty_output(out_dir, allow_inputs=allow_existing_inputs)
    validate_tilek_run(run)
    metadata = dict(metadata or {})
    if metadata.keys() - {"identity", "provenance", "ended_at_s", "metrics", "ticks_per_second"}:
        raise ValueError("metadata cannot override authoritative manifest fields")
    binding = run["events"][0]["payload"]["visual_projection"]
    metadata["provenance"] = {**metadata.get("provenance", {}), **binding}
    tps = metadata.get("ticks_per_second", 3_000_000)
    if type(tps) is not int or tps <= 0:
        raise ValueError("timebase must be a positive integer")
    _interval_ticks(chunk_duration_s, tps)
    _interval_ticks(snapshot_interval_s, tps)
    end_s = _end_seconds(run, metadata)
    return _write_bundle(run, out_dir, metadata, end_s, chunk_duration_s, snapshot_interval_s, tps)
