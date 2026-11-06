"""Shared pytest fixtures: contract files from the repository root."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.actors import ActorRegistry
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle, load_contract_bundle
from app.settings import default_contracts_dir


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
