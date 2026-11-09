"""The production materialization adapter persists reproducible real inputs."""

from pathlib import Path

import pytest

from app.api.context import ApiContext
from app.api.worker import materialize_job
from app.data.history import HistoryArtifact
from app.storage.artifacts import ArtifactStore
from tests.api.test_processor import _constant_history


def test_materialize_persists_scenario_history_and_reuses_input_hashes(
    tmp_path: Path, contracts_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = HistoryArtifact(_constant_history())
    monkeypatch.setattr("app.data.history.history_artifact", lambda: artifact)

    def prohibit_regeneration() -> None:
        raise AssertionError("API must reuse the immutable history artifact")

    monkeypatch.setattr("app.data.history.generate_history", prohibit_regeneration)
    store = ArtifactStore(tmp_path)
    context = ApiContext.create(store, contracts_dir)
    job = context.job("materialize", {"profile": "large-normal", "horizon_s": 3600})
    first, repeated = materialize_job(job), materialize_job(job)
    assert first == repeated
    assert first["orders"] == 240  # Technical specification normal profile:240 orders/hour.
    assert first["shortened_run"] is False
    scenario = store.read_json("scenarios", first["scenario_id"])
    assert scenario["horizon_s"] == 3600
    assert len(scenario["orders"]) == 240
    assert store.read_bytes("histories", first["history_id"]).startswith(b"date,sku_id,")
    assert first["assignment_id"] == context.assignment_id
    assert first["history_id"] == artifact.sha256
