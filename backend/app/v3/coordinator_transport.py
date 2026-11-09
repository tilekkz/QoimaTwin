"""C-only chunk transport; strict reads restore all native resources before semantic validation."""

from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_run import _validate_native, validate_coordinator_run
from app.v3.coordinator_run_schema import PUBLICATION_VERSION, RUN_FIELDS, TRANSPORT_VERSION
from app.v3.coordinator_transport_files import (
    closed_inventory,
    publish,
    put,
    read_file,
    read_json,
    require_output,
)
from app.v3.coordinator_transport_schema import EVENT_CHUNK_TICKS, validate_manifest
from app.v3.native_read_context import _NativeReadContext


def write_coordinator_run(run: dict[str, Any], out_dir: Path, *, inputs: bytes) -> dict[str, Any]:
    require_output(out_dir, inputs)
    validate_coordinator_run(run, inputs=inputs)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".coordinator-stage-", dir=out_dir.parent) as temporary:
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
        **{
            key: run[key]
            for key in ("engine_version", "run_id", "input_hash", "registry_common_hash")
        },
        "inputs": put(stage, "inputs.json", inputs),
        "catalog": put(stage, "catalog.json", canonical_bytes(catalog)),
        "event_chunks": _events(stage, outcome["events"]),
        "snapshot_chunks": _snapshots(stage, outcome),
    }
    validate_manifest(manifest)
    put(stage, "manifest.json", canonical_bytes(manifest))
    return manifest


def _events(stage: Path, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[event["tick"] // EVENT_CHUNK_TICKS].append(event)
    refs = []
    for index, rows in sorted(groups.items()):
        ref = put(stage, f"events/{index:08d}.json", canonical_bytes(rows))
        ref.update(
            start_tick=index * EVENT_CHUNK_TICKS,
            end_tick=(index + 1) * EVENT_CHUNK_TICKS,
            first_seq=rows[0]["seq"],
            last_seq=rows[-1]["seq"],
        )
        refs.append(ref)
    return refs


def _snapshots(stage: Path, outcome: dict[str, Any]) -> list[dict[str, Any]]:
    points: dict[int, tuple[dict[str, Any], list[str]]] = {}
    for role in ("checkpoint", "at_horizon", "at_end"):
        values = outcome["checkpoints"] if role == "checkpoint" else [outcome[role]]
        for point in values:
            tick = point["tick"]
            if tick not in points:
                points[tick] = point, []
            previous, roles = points[tick]
            if canonical_bytes(previous) != canonical_bytes(point):
                raise ValueError("Coordinator captured roles disagree at the same settled tick")
            roles.append(role)
    refs = []
    for tick, (point, roles) in sorted(points.items()):
        ref = put(stage, f"snapshots/{tick:016d}.json", canonical_bytes(point))
        ref.update(tick=tick, last_seq=point["last_seq"], roles=roles)
        refs.append(ref)
    return refs


def read_coordinator_run(out_dir: Path) -> dict[str, Any]:
    return _read_coordinator_context(out_dir).run()


def _read_coordinator_context(out_dir: Path) -> _NativeReadContext:
    path = out_dir / "manifest.json"
    if (
        out_dir.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**21
    ):
        raise ValueError("Missing or invalid bounded coordinator manifest")
    raw = path.read_bytes()
    manifest = parse_json(raw)
    if canonical_bytes(manifest) != raw:
        raise ValueError("Coordinator manifest bytes are not canonical")
    refs = validate_manifest(manifest)
    closed_inventory(out_dir, refs)
    inputs = read_file(out_dir, manifest["inputs"])
    run = read_json(out_dir, manifest["catalog"])
    if type(run) is not dict or run.keys() != RUN_FIELDS or type(run.get("outcome")) is not dict:
        raise ValueError("Coordinator catalog has no native outcome metadata")
    metadata = {
        "status",
        "business_complete_tick",
        "resource_drained_tick",
        "observation_end_tick",
        "staffing_status",
        "constraint_violations",
    }
    if run["outcome"].keys() != metadata:
        raise ValueError("Coordinator catalog cannot contain mutable history or unknown metadata")
    run["outcome"]["events"] = _read_events(out_dir, manifest["event_chunks"])
    _read_snapshots(out_dir, manifest["snapshot_chunks"], run["outcome"])
    for key in ("engine_version", "run_id", "input_hash", "registry_common_hash"):
        if manifest[key] != run.get(key):
            raise ValueError("Coordinator catalog and manifest identity differ")
    return _validate_native(run, inputs=inputs)


def _read_events(root: Path, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for ref in refs:
        rows = read_json(root, ref)
        if type(rows) is not list or not rows or any(type(row) is not dict for row in rows):
            raise ValueError("Coordinator event chunk requires a nonempty native event array")
        if (rows[0].get("seq"), rows[-1].get("seq")) != (ref["first_seq"], ref["last_seq"]):
            raise ValueError("Coordinator chunk observed sequence differs")
        if any(
            type(row.get("tick")) is not int
            or not ref["start_tick"] <= row["tick"] < ref["end_tick"]
            for row in rows
        ):
            raise ValueError("Coordinator events escape their half-open integer chunk")
        result.extend(rows)
    return result


def _read_snapshots(root: Path, refs: list[dict[str, Any]], outcome: dict[str, Any]) -> None:
    outcome["checkpoints"] = []
    for ref in refs:
        point = read_json(root, ref)
        if type(point) is not dict or (point.get("tick"), point.get("last_seq")) != (
            ref["tick"],
            ref["last_seq"],
        ):
            raise ValueError("Coordinator captured tick or event watermark differs")
        for role in ref["roles"]:
            if role == "checkpoint":
                outcome["checkpoints"].append(point)
            else:
                outcome[role] = point
