"""Raw hashes and half-open windows describe actual finite observations."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_run import build_flow_run
from app.v3.flow_transport import captured_checkpoint, event_window, read_flow_run, write_flow_run
from tests.v3.test_flow_run_fixtures import sample


def test_boundary_60_is_in_next_half_open_chunk_and_checkpoint_is_actual(tmp_path: Path) -> None:
    inputs, outcome = sample(True)
    run = build_flow_run(inputs, outcome)
    manifest = write_flow_run(run, tmp_path, inputs=inputs.frozen_bytes, max_chunk_bytes=16_384)
    assert read_flow_run(tmp_path) == run
    for descriptor in manifest["event_chunks"]:
        raw = (tmp_path / descriptor["path"]).read_bytes()
        assert len(raw) <= 16_384
        for event in json.loads(raw)["items"]:
            assert descriptor["start_tick"] <= event["tick"] < descriptor["end_tick"]
            if event["kind"] == "intake_handoff":
                assert event["tick"] == descriptor["start_tick"] == 60_000_000
    view = captured_checkpoint(tmp_path, 61_000_000)
    assert view == run["at_end"]
    assert not any(e["kind"] == "shipped" for e in run["events"])
    with pytest.raises(ValueError, match="captured"):
        captured_checkpoint(tmp_path, 60_500_000)
    rows = event_window(tmp_path, 60_000_000, 61_000_000)
    assert any(e["kind"] == "intake_handoff" for e in rows)
    assert all(60_000_000 <= e["tick"] < 61_000_000 for e in rows)
    with pytest.raises(ValueError, match="at most"):
        event_window(tmp_path, 0, 61_000_000)


@pytest.mark.parametrize("defect", ["raw", "traversal", "identity"])
def test_reader_rejects_corrupt_bytes_paths_and_identity(tmp_path: Path, defect: str) -> None:
    inputs, outcome = sample(True)
    manifest = write_flow_run(build_flow_run(inputs, outcome), tmp_path, inputs=inputs.frozen_bytes)
    if defect == "raw":
        (tmp_path / manifest["event_chunks"][0]["path"]).write_bytes(b"{}")
    else:
        value = deepcopy(manifest)
        if defect == "traversal":
            value["catalog"]["path"] = "../outside.json"
        else:
            value["run_id"] = "0" * 64
        (tmp_path / "manifest.json").write_bytes(canonical_bytes(value))
    with pytest.raises(ValueError):
        read_flow_run(tmp_path)


def test_too_small_raw_chunk_limit_retains_inputs_without_success_manifest(tmp_path: Path) -> None:
    inputs, outcome = sample(True)
    with pytest.raises(ValueError, match="byte limit"):
        write_flow_run(
            build_flow_run(inputs, outcome),
            tmp_path,
            inputs=inputs.frozen_bytes,
            max_chunk_bytes=13,
        )
    assert (tmp_path / "inputs.json").read_bytes() == inputs.frozen_bytes
    assert not (tmp_path / "manifest.json").exists()
