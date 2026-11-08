"""Compile exact source choices before publishing a connected receipt run."""

from pathlib import Path

from app.errors import require_empty_output
from app.storage.canonical_json import parse_json
from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.receipt_profile import compile_receipt_profile
from app.v3.receipt_run_execute import simulate_receipt


def simulate_receipt_file(bundle_path: Path, profile_path: Path, out: Path) -> Json:
    require_empty_output(out)
    document = parse_json(profile_path.read_bytes())
    bundle = load_v3_bundle(bundle_path)
    conveyor = load_conveyor_source(bundle)
    inputs = compile_receipt_profile(bundle, conveyor, document)
    return simulate_receipt(inputs, conveyor, out)
