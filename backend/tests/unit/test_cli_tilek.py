"""The explicit Tilek command produces an accepted, source-bound inline visual run."""

import json
from pathlib import Path

import pytest

from app.cli import main
from app.data.history import HistoryArtifact
from app.exporter.tilek_validation import validate_tilek_run
from app.storage.canonical_json import sha256_hex


def test_tilek_command_has_distinct_identity_and_inline_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("app.data.history.history_artifact", lambda: HistoryArtifact(b"test\n"))
    assert (
        main(
            [
                "simulate",
                "--profile",
                "large-normal",
                "--horizon-s",
                "1",
                "--out",
                str(tmp_path),
                "--format",
                "tilek-v2",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    run = json.loads((tmp_path / "run.json").read_bytes())
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    validate_tilek_run(run)
    assert run["schema_version"] == "2.0"
    assert run["run_id"] == report["run_id"] == sha256_hex(manifest["identity"])
    assert manifest["identity"]["wire_version"] == "tilek-visual-v1"
    assert manifest["provenance"]["source_run_id"] != run["run_id"]
