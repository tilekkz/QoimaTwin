"""Exported tote identities follow the configured physical pool."""

from dataclasses import replace
from pathlib import Path

from app.contracts.loader import ContractBundle
from app.exporter.catalog import cargo_catalog, initial_state
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture


def test_exported_pool_uses_configured_totes(bundle: ContractBundle, contracts_dir: Path) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = replace(inputs, config=inputs.config.model_copy(update={"totes_total": 2}))
    engine = Engine(inputs, check_invariants=True)
    engine.run()
    assert initial_state(engine)["tote_pool"] == ["T001", "T002"]
    assert [c["cargo_id"] for c in cargo_catalog(engine) if c["kind"] == "tote"] == [
        "T001",
        "T002",
    ]
