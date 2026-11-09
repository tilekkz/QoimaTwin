"""Publish a source-compiled finite calendar for a later explicit coordinator run."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_source import load_conveyor_source
from app.v3.coordinator_calendar import materialize_calendar
from app.v3.coordinator_calendar_io import parse_calendar
from app.v3.coordinator_cli_evidence import reserve
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.inputs import load_v3_bundle


def _write(path: Path, raw: bytes) -> dict[str, Any]:
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def materialize_coordinator_calendar_file(
    inputs_path: Path,
    profile_path: Path,
    calendar_path: Path,
    out: Path,
) -> dict[str, Any]:
    reserve(out)
    document = parse_json(profile_path.read_bytes())
    calendar = parse_calendar(parse_json(calendar_path.read_bytes()))
    materialized = materialize_calendar(document, calendar)
    bundle = load_v3_bundle(inputs_path)
    conveyor = load_conveyor_source(bundle)
    compiled = compile_coordinator_profile(bundle, conveyor, parse_json(materialized.choices_bytes))
    choices = parse_json(compiled.frozen_bytes)["choices"]
    reserve(out)
    out.mkdir(parents=True, exist_ok=True)
    files = [
        _write(out / "calendar.json", materialized.calendar_bytes),
        _write(out / "profile.json", canonical_bytes(choices)),
        _write(out / "inputs.json", compiled.frozen_bytes),
    ]
    report = {
        "status": "passed",
        "data_kind": "explicit_coordinator_calendar",
        "input_hash": compiled.input_hash,
        "offered_workload_hash": materialized.offered_workload_hash,
        "source_revision": bundle.source_revision,
        "horizon_tick": compiled.horizon_tick,
        "end_tick": compiled.end_tick,
        "counts": dict(materialized.counts),
        "operational_admission": False,
        "scope": "explicit_existing_population; source_compiled; no_engine_execution",
    }
    _write(out / "manifest.json", canonical_bytes({**report, "files": files}))
    return {**report, "manifest": "manifest.json"}
