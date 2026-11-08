"""Readback independently binds catalog, both clocks and original source artifact identity."""

from app.storage.canonical_json import parse_json
from app.v3.interface import Json
from app.v3.receipt_run_journal import same
from app.v3.whole_run_inputs import load_whole_inputs
from app.v3.whole_run_values import catalog


def validate_input_binding(run: Json, raw: bytes) -> None:
    inputs = load_whole_inputs(raw)
    expected = {
        "input_hash": inputs.input_hash,
        "physical_input_hash": inputs.physical_input_hash,
        "horizon_tick": inputs.horizon_tick,
        "end_tick_limit": inputs.end_tick,
    }
    same({k: run[k] for k in expected}, expected, "Whole frozen input identity or clock differs")
    physical = parse_json(raw)["physical_inputs"]
    same(run["catalog"], catalog(physical), "Whole catalog differs from verified physical inputs")
