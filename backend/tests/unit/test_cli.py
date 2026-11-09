"""CLI `validate-contracts` returns a JSON report and a meaningful exit code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli import main


def test_validate_contracts_passes_on_repository_files(
    contracts_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate-contracts", "--contracts-dir", str(contracts_dir)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["summary"] == {
        "layout_version": "qoima-72x48-v2",
        "picker_nodes": 184,
        "picker_edges": 205,
        "slots": 864,
        "conveyor_cells": 179,
        "actors": 24,
    }


def test_validate_contracts_fails_on_missing_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate-contracts", "--contracts-dir", str(tmp_path / "none")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert report["issues"]
