"""Freeze explicit conveyor inputs before running the invariant-checked component."""

from pathlib import Path
from typing import Any

from app.errors import require_empty_output
from app.storage.canonical_json import parse_json
from app.v3.belt_engine import BeltEngine
from app.v3.belt_export import publish_trace, write_file
from app.v3.belt_profile import compile_belt_profile
from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle


def simulate_conveyor(bundle_path: Path, profile_path: Path, out: Path) -> dict[str, Any]:
    require_empty_output(out)
    bundle = load_v3_bundle(bundle_path)
    source = load_conveyor_source(bundle)
    inputs = compile_belt_profile(bundle, source, parse_json(profile_path.read_bytes()))
    out.mkdir(parents=True, exist_ok=True)
    input_file = write_file(out / "inputs.json", inputs.frozen_bytes)
    outcome = BeltEngine(source, inputs.jobs, check_invariants=True).run(
        inputs.horizon_tick,
        inputs.end_tick,
    )
    return publish_trace(inputs, outcome, out, input_file)
