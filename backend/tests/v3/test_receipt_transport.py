"""Raw immutable receipt bundles retain inclusive captures and half-open event buckets."""

from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_transport import (
    captured_checkpoint,
    event_window,
    read_receipt_run,
    write_receipt_run,
)
from tests.v3.test_receipt_run_fixtures import sample


def test_bundle_roundtrip_and_half_open_windows(tmp_path: Path) -> None:
    inputs, outcome = sample()
    run = build_receipt_run(inputs, outcome)
    manifest = write_receipt_run(run, tmp_path, inputs=inputs.frozen_bytes)
    assert canonical_bytes(read_receipt_run(tmp_path)) == canonical_bytes(run)
    assert captured_checkpoint(tmp_path, 30_000_000) == run["checkpoints"][1]
    assert all(0 <= e["tick"] < 60_000_000 for e in event_window(tmp_path, 0, 60_000_000))
    assert all(
        d["start_tick"] <= d["first_tick"] <= d["last_tick"] < d["end_tick"]
        for d in manifest["event_chunks"]
    )
    with pytest.raises(ValueError, match="captured"):
        captured_checkpoint(tmp_path, 31_000_000)
    with pytest.raises(ValueError):
        event_window(tmp_path, 0, 60_000_001)
    with pytest.raises(ValueError):
        write_receipt_run(run, tmp_path, inputs=inputs.frozen_bytes)


@pytest.mark.parametrize("tamper", ["bytes", "traversal", "bound"])
def test_reader_rejects_corruption_even_for_earliest_window(tmp_path: Path, tamper: str) -> None:
    inputs, outcome = sample()
    manifest = write_receipt_run(
        build_receipt_run(inputs, outcome), tmp_path, inputs=inputs.frozen_bytes
    )
    descriptor = manifest["event_chunks"][-1]
    if tamper == "bytes":
        path = tmp_path / descriptor["path"]
        path.write_bytes(path.read_bytes() + b" ")
    else:
        if tamper == "traversal":
            descriptor["path"] = "events/../../foreign.json"
        else:
            descriptor["end_tick"] -= 1
        (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        event_window(tmp_path, 0, 1)


def test_catalog_integer_boolean_alias_is_not_input_binding(tmp_path: Path) -> None:
    inputs, outcome = sample()
    run = build_receipt_run(inputs, outcome)
    run["catalog"]["actors"][1]["available_tick"] = False
    with pytest.raises(ValueError):
        write_receipt_run(run, tmp_path, inputs=inputs.frozen_bytes)
    assert not (tmp_path / "manifest.json").exists()
    assert isinstance(parse_json(inputs.frozen_bytes), dict)
