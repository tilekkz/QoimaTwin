"""Shared pytest fixtures: contract files from the repository root."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.contracts.actors import ActorRegistry
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle, load_contract_bundle
from app.data.history import HistoryArtifact, history_artifact, history_by_hash
from app.data.scenario_materializer import MaterializedScenario, materialize
from app.settings import default_contracts_dir
from app.simulation.engine import Engine, RunOutcome
from app.simulation.fixtures import fixture_inputs, load_fixture


@pytest.fixture(scope="session", autouse=True)
def isolated_history_cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Tests never read or write the real user cache, including subprocess inheritance."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("QOIMA_HISTORY_CACHE_DIR", str(tmp_path_factory.mktemp("history-cache")))
        yield


@pytest.fixture(autouse=True)
def clear_history_memory_cache(isolated_history_cache: None) -> Iterator[None]:
    """Keep monkeypatched generators independent of earlier test artifacts."""
    from app.data.history import history_artifact

    history_artifact.cache_clear()
    yield
    history_artifact.cache_clear()


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    return default_contracts_dir()


@pytest.fixture(scope="session")
def bundle(contracts_dir: Path) -> ContractBundle:
    return load_contract_bundle(contracts_dir)


@pytest.fixture(scope="session")
def layout(bundle: ContractBundle) -> Layout:
    return bundle.layout


@pytest.fixture(scope="session")
def config(bundle: ContractBundle) -> SimulationConfig:
    return bundle.config


@pytest.fixture(scope="session")
def actors(bundle: ContractBundle) -> ActorRegistry:
    return bundle.actors


@pytest.fixture(scope="session")
def analytical_fixture(contracts_dir: Path) -> dict[str, Any]:
    """Read-only analytical oracle; mutation tests must make their own copy."""
    return load_fixture(contracts_dir)


@pytest.fixture(scope="session")
def analytical_run(
    bundle: ContractBundle, analytical_fixture: dict[str, Any]
) -> tuple[Engine, RunOutcome]:
    """Completed engine shared only by inspection tests, never advanced or modified."""
    engine = Engine(fixture_inputs(bundle, analytical_fixture), check_invariants=True)
    return engine, engine.run()


@pytest.fixture(scope="session")
def normal_materialization(config: SimulationConfig) -> MaterializedScenario:
    """Immutable inputs; reproducibility tests still construct their second input independently."""
    return materialize("large-normal", 3600, config)


@pytest.fixture(scope="session")
def synthetic_history() -> Any:
    """Generate once per worker; each publisher receives a private copy below."""
    return history_by_hash(history_artifact().sha256)


@pytest.fixture
def cached_materialization_history(synthetic_history: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache publisher inputs; generator tests always exercise the real generator."""
    artifact = HistoryArtifact(
        synthetic_history.to_csv(index=False, lineterminator="\n").encode("utf-8")
    )
    monkeypatch.setattr("app.data.history.history_artifact", lambda: artifact)
