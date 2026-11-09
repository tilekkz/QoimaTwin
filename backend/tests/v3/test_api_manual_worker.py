"""Failures retain evidence without references; tiny real engine proves the seam."""

from pathlib import Path

import pytest

from app.api.context import Job
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.v3.api_manual_inputs import confined, freeze_profile
from app.v3.api_manual_worker import manual_job
from app.v3.execution import ManualEngine
from app.v3.settings import default_inputs
from tests.v3.test_execution_manual import fixture, tick


def test_failed_tiny_actual_engine_retains_inputs_without_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    frozen = freeze_profile(store, default_inputs())
    job = Job("manual-v3", {"manual_bundle_id": frozen.bundle_id}, str(tmp_path), "", "", "")

    def failing_pipeline(source: Path, proposal: Path, output: Path) -> dict[str, str]:
        assert (source / "provenance.json").is_file() and proposal.is_file()
        profile, graph = fixture()
        result = ManualEngine(profile, graph, check_invariants=True).run(tick(25), tick(40))
        assert result.at_end.status == "complete"
        assert result.at_end.stock_units == (("SKU1", 24),)
        raise ValueError("private server path must not leak")

    monkeypatch.setattr("app.v3.api_manual_worker.simulate_manual", failing_pipeline)
    with pytest.raises(InvalidInputError, match="manual proposal validation failed") as error:
        manual_job(job)
    assert "private" not in str(error.value)
    assert list((tmp_path / "manual-v3-evidence").glob("*/failure.json"))
    assert list((tmp_path / "manual-v3-evidence").glob("*/source/proposal.json"))
    assert not (tmp_path / "runs").exists() and not (tmp_path / "requests").exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "a\\b", "."])
def test_manual_restore_paths_are_confined(tmp_path: Path, name: str) -> None:
    with pytest.raises(InvalidInputError):
        confined(tmp_path, name)
