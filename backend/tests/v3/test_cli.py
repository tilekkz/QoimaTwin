"""V3 commands operate on source-bound proposal inputs without loading V2 contracts."""

import json
from pathlib import Path

import pytest

from app.cli import build_parser, main


def test_parent_help_lists_v3_tools() -> None:
    assert "v3" in build_parser().format_help()


def test_v3_validate_reports_source_counts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["v3", "validate"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["data_kind"] == "static_geometry_proposal"
    assert report["baseline"]["handling_units"] == 530
    assert report["baseline"]["quantity_units"] == 12256
    assert report["baseline"]["gross_mass_kg"] == 9403.85
    assert report["layout_version"] == "qoima-144x72-v3-proposal"
    assert not report["operational_admission"]


def test_v3_export_is_an_offline_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["v3", "catalog", "--out", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert (tmp_path / "manifest.json").is_file()
    assert not (tmp_path / "run.json").exists()


def test_v3_missing_input_rejected_without_v2_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["v3", "validate", "--inputs", str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert report["layout_version"] == "qoima-144x72-v3-proposal"
    assert not report["operational_admission"]


def test_v3_simulation_requires_implemented_profile(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["v3", "simulate"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert "invalid choice" in report["error"]["message"]
