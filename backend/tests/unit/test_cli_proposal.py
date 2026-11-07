"""Proposal export is explicit and retains the accepted v2 default."""

import json
from pathlib import Path

import pytest

from app.cli import build_parser, main
from app.data.history import HistoryArtifact


def test_proposal_format_and_inline_are_explicit_options() -> None:
    common = ["simulate", "--profile", "large-normal", "--horizon-s", "1", "--out", "run"]
    default = build_parser().parse_args(common)
    proposal = build_parser().parse_args([*common, "--format", "proposal", "--include-inline"])
    assert default.output_format == "v2"
    assert default.include_inline is False
    assert proposal.output_format == "proposal"
    assert proposal.include_inline is True


@pytest.mark.parametrize("include_inline", [False, True])
def test_proposal_command_publishes_validated_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    include_inline: bool,
) -> None:
    monkeypatch.setattr("app.data.history.history_artifact", lambda: HistoryArtifact(b"test\n"))
    arguments = [
        "simulate",
        "--profile",
        "large-normal",
        "--horizon-s",
        "1",
        "--out",
        str(tmp_path),
        "--format",
        "proposal",
    ]
    if include_inline:
        arguments.append("--include-inline")
    assert main(arguments) == 0
    report = json.loads(capsys.readouterr().out)
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    assert manifest["run_id"] == report["run_id"]
    assert manifest["contract_status"] == "proposal"
    assert manifest["identity"]["wire_version"] == "2.1-proposal"
    assert (tmp_path / "run.json").exists() is include_inline
