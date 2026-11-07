"""Publication validates the real export exactly once at the writer boundary."""

from pathlib import Path
from typing import Any

import pytest

import app.exporter.run as run_module
from app.api.publication import publish_run
from app.contracts.loader import ContractBundle
from app.exporter.validation import validate_run
from app.simulation.engine import Engine
from app.storage.artifacts import ArtifactStore
from tests.builders import run_inputs, scenario


def test_publication_writer_validates_the_real_run_once(
    tmp_path: Path, bundle: ContractBundle, contracts_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def tracked_validate(run: dict[str, Any]) -> None:
        calls.append(run["run_id"])
        validate_run(run)

    monkeypatch.setattr(run_module, "validate_run", tracked_validate)
    engine = Engine(
        run_inputs(bundle, contracts_dir, scenario([], horizon_s=1)), check_invariants=True
    )
    identifier = publish_run(ArtifactStore(tmp_path), engine, engine.run())
    assert calls == [identifier]
