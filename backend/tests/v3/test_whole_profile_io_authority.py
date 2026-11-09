"""Valid source receipts and exact typed authority remain checked on cache hits."""

import json
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle
from app.v3.settings import default_inputs
from app.v3.whole_cli_evidence import freeze_request
from app.v3.whole_profile_io import compile_whole_profile
from tests.v3.test_whole_profile_io_schema import document


def test_valid_request_and_cached_bytes_do_not_hide_typed_state_corruption(tmp_path: Path) -> None:
    bundle = load_v3_bundle(default_inputs())
    conveyor = load_conveyor_source(bundle)
    compiled = compile_whole_profile(bundle, conveyor, document())
    out = tmp_path / "valid"
    receipt_hash = freeze_request(compiled, out)
    receipt = json.loads((out / "request.json").read_bytes())
    assert receipt_hash == sha256((out / "request.json").read_bytes()).hexdigest()
    assert receipt["input_hash"] == compiled.run_inputs.input_hash
    assert (out / "run/inputs.json").read_bytes() == compiled.run_inputs.frozen_bytes
    profile = compiled.run_inputs.profile
    flow = profile.receipts.flow
    actor = replace(flow.actors[0], speed_m_s=cast(Fraction, 1))
    altered_flow = replace(flow, actors=(actor, *flow.actors[1:]))
    altered = replace(profile, receipts=replace(profile.receipts, flow=altered_flow))
    bad = replace(compiled, run_inputs=replace(compiled.run_inputs, profile=altered))
    with pytest.raises(ValueError, match=r"exact.*scalar"):
        freeze_request(bad, tmp_path / "typed-corruption")
    fresh = compile_whole_profile(bundle, conveyor, document())
    assert fresh.run_inputs.profile is not compiled.run_inputs.profile
    assert fresh.run_inputs.frozen_bytes == compiled.run_inputs.frozen_bytes
    assert not (tmp_path / "typed-corruption").exists()
