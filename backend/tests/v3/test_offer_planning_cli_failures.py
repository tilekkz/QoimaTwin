"""Bounded orchestration failures preserve raw and partial stage evidence."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.cli import main
from app.v3 import offer_planning_cli_pipeline as pipeline
from app.v3.offer_planning_cli_storage import put, read_regular
from tests.v3.test_offer_planning_cli_fixtures import arguments


def test_calculation_failure_preserves_frozen_request_and_partial_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "out"

    def interrupted(
        root: Path, model: str, raw: dict[str, bytes], request: bytes
    ) -> dict[str, Any]:
        assert (root / "request.json").read_bytes() == request
        assert (root / "raw/history.csv").read_bytes() == raw["history.csv"]
        assert model == "mean28"
        put(root, "history.json", b"partial-stage-test-sentinel")
        raise ValueError("Injected interruption after frozen request and first stage")

    monkeypatch.setattr(pipeline, "_calculate", interrupted)
    assert main(arguments(tmp_path / "caller", output)) == 1
    assert (output / "history.json").read_bytes() == b"partial-stage-test-sentinel"
    assert (output / "request.json").is_file()
    assert len(list((output / "raw").iterdir())) == 4
    failure = json.loads((output / "failure.json").read_bytes())
    assert failure["valid_manifest"] is False
    assert failure["scope"] == "incomplete_planning_attempt"
    assert not (output / "manifest.json").exists()


def test_actual_future_stream_argument_is_not_accepted(tmp_path: Path) -> None:
    output = tmp_path / "out"
    args = arguments(tmp_path / "caller", output)
    assert main([*args, "--actual-test-stream", "not-accepted.csv"]) == 1
    assert not output.exists()


def test_hardlinked_input_is_not_accepted(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"unchanged")
    alias = tmp_path / "alias"
    alias.hardlink_to(original)
    with pytest.raises(ValueError, match="unshared planning file"):
        read_regular(alias)
    assert original.read_bytes() == b"unchanged"
