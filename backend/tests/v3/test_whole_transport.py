"""A complete new namespace binds exact frozen inputs and finite raw chunks on readback."""

from pathlib import Path

import pytest

from app.v3.receipt_transport import read_receipt_run
from app.v3.whole_run import build_whole_run
from app.v3.whole_transport import (
    captured_checkpoint,
    event_window,
    read_whole_run,
    write_whole_run,
)
from tests.v3.test_receipt_flow_fixtures import SECOND
from tests.v3.test_whole_run_fixtures import sample


def test_native_bundle_roundtrip_and_old_reader_rejects_namespace(tmp_path: Path) -> None:
    inputs, outcome = sample()
    run = build_whole_run(inputs, outcome, validate=False)
    manifest = write_whole_run(run, tmp_path, inputs=inputs.frozen_bytes)
    assert manifest["physical_input_hash"] == inputs.physical_input_hash
    assert read_whole_run(tmp_path) == run
    with pytest.raises(ValueError, match=r"schema"):
        read_receipt_run(tmp_path)
    with pytest.raises(ValueError, match=r"empty"):
        write_whole_run(run, tmp_path, inputs=inputs.frozen_bytes)


def test_only_captured_seek_and_half_open_event_window(tmp_path: Path) -> None:
    inputs, outcome = sample()
    write_whole_run(
        build_whole_run(inputs, outcome, validate=False), tmp_path, inputs=inputs.frozen_bytes
    )
    assert captured_checkpoint(tmp_path, 30 * SECOND)["tick"] == 30 * SECOND
    with pytest.raises(ValueError, match=r"captured"):
        captured_checkpoint(tmp_path, 31 * SECOND)
    window = event_window(tmp_path, 47 * SECOND, 52 * SECOND)
    assert any(e["kind"] == "whole_shipped" for e in window)
    assert not any(e["kind"] == "whole_returned" for e in window)


def test_changed_input_clock_rejects_before_publishing_any_file(tmp_path: Path) -> None:
    from app.storage.canonical_json import canonical_bytes, parse_json

    inputs, outcome = sample()
    value = parse_json(inputs.frozen_bytes)
    value["end_tick"] += 1
    with pytest.raises(ValueError, match=r"input|clock"):
        write_whole_run(
            build_whole_run(inputs, outcome, validate=False),
            tmp_path,
            inputs=canonical_bytes(value),
        )
    assert list(tmp_path.iterdir()) == []
