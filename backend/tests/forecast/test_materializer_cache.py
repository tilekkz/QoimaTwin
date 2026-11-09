"""Publishing two scenarios reuses the immutable history source bytes."""

from pathlib import Path

import pytest

from app.contracts.config import SimulationConfig
from app.data import history
from app.data.scenario_materializer import materialize, write_materialized


def test_materializer_uses_frozen_history_cache(
    config: SimulationConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = b"date,sku_id,visits,units,split\n"
    artifact = history.HistoryArtifact(expected)
    monkeypatch.setattr(history, "history_artifact", lambda: artifact)

    def forbidden_generation() -> None:
        pytest.fail("publishing an existing history must not regenerate orders")

    monkeypatch.setattr(history, "generate_history", forbidden_generation)
    scenario = materialize("large-normal", 3600, config)
    for variant in ("a", "b"):
        write_materialized(scenario, tmp_path / variant)
        assert (tmp_path / variant / "history_daily.csv").read_bytes() == expected
