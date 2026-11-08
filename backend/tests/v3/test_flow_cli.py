"""The real strict compiler precedes output and frozen inputs precede engine construction."""

from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3 import cli_lightflow
from app.v3.flow_profile import compile_light_profile
from app.v3.flow_run_validation import run_identity
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import EXAMPLE, document


@pytest.mark.parametrize("stage", ["constructor", "run"])
def test_frozen_inputs_survive_failed_engine_constructor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    expected = compile_light_profile(source_bundle(), source_catalog(), document()).frozen_bytes
    out = tmp_path / "run"

    class FailedEngine:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            assert (out / "inputs.json").read_bytes() == expected
            if stage == "constructor":
                raise RuntimeError("deliberate construction failure")

        def run(self, *args: Any) -> None:
            raise RuntimeError("deliberate runtime failure")

    monkeypatch.setattr(cli_lightflow, "LightFlowEngine", FailedEngine)
    with pytest.raises(RuntimeError, match="deliberate"):
        cli_lightflow.simulate_light_file(Path("data/v3-proposal"), EXAMPLE, out)
    assert (out / "inputs.json").exists() and not (out / "manifest.json").exists()


def test_bad_json_never_creates_output_and_nonempty_is_preserved(tmp_path: Path) -> None:
    profile = tmp_path / "bad.json"
    profile.write_text('{"schema_id":1,"schema_id":2}')
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        cli_lightflow.simulate_light_file(Path("data/v3-proposal"), profile, out)
    assert not out.exists()
    out.mkdir()
    (out / "keep").write_bytes(b"original")
    with pytest.raises(ValueError):
        cli_lightflow.simulate_light_file(Path("data/v3-proposal"), EXAMPLE, out)
    assert (out / "keep").read_bytes() == b"original"


def test_canonical_set_permutations_publish_identical_real_empty_runs(tmp_path: Path) -> None:
    value = document()
    value.update(orders=[], horizon_tick=1, end_tick=1)
    profile = tmp_path / "profile.json"
    profile.write_bytes(canonical_bytes(value))
    first = cli_lightflow.simulate_light_file(Path("data/v3-proposal"), profile, tmp_path / "first")
    for key in ("actors", "owners", "materials", "recipes"):
        value[key].reverse()
    profile.write_bytes(canonical_bytes(value))
    second = cli_lightflow.simulate_light_file(
        Path("data/v3-proposal"), profile, tmp_path / "second"
    )
    assert first["run_id"] == second["run_id"]
    for path in (tmp_path / "first").rglob("*.json"):
        assert (
            path.read_bytes()
            == (tmp_path / "second" / path.relative_to(tmp_path / "first")).read_bytes()
        )
    value["horizon_tick"] = value["end_tick"] = 2
    changed = compile_light_profile(source_bundle(), source_catalog(), value)
    assert run_identity(changed.input_hash) != first["run_id"]
