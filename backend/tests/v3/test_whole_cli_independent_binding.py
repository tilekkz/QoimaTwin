"""A public request receipt must bind choices to the actual compiled source envelope."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle
from app.v3.settings import default_inputs
from app.v3.whole_cli_evidence import freeze_request
from app.v3.whole_profile_io import CompiledWholeProfile, compile_whole_profile
from tests.v3.test_whole_profile_io_schema import document


@pytest.fixture(scope="module")
def actual_compiled() -> CompiledWholeProfile:
    bundle = load_v3_bundle(default_inputs())
    return compile_whole_profile(bundle, load_conveyor_source(bundle), document())


@pytest.mark.parametrize("field", ["choices", "horizon", "input_hash"])
def test_request_rejects_independently_rehashed_choices_or_stale_compiled_envelope(
    actual_compiled: CompiledWholeProfile, tmp_path: Path, field: str
) -> None:
    compiled = actual_compiled
    if field == "choices":
        choices = parse_json(compiled.choices_bytes)
        choices["whole_times"]["pickup"] += 1
        raw = canonical_bytes(choices)
        compiled = replace(compiled, choices_bytes=raw, choices_sha256=sha256(raw).hexdigest())
    else:
        inputs = compiled.run_inputs
        changed = (
            replace(inputs, horizon_tick=inputs.horizon_tick + 1)
            if field == "horizon"
            else replace(inputs, input_hash="a" * 64)
        )
        compiled = replace(compiled, run_inputs=changed)
    out = tmp_path / "receipt"
    with pytest.raises(ValueError):
        freeze_request(compiled, out)
    assert not out.exists() or not any(out.iterdir())
