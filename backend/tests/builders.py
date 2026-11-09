"""Helpers that build small, explicit run inputs on the full layout."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from app.contracts.loader import ContractBundle
from app.contracts.scenario import Scenario
from app.simulation.context import RunInputs
from app.simulation.engine import Engine, RunOutcome
from app.simulation.fixtures import fixture_inputs, load_fixture

ZERO_HASH = "0" * 64


def scenario(
    orders: list[dict[str, Any]],
    receipts: list[dict[str, Any]] | None = None,
    horizon_s: float = 3600,
) -> Scenario:
    return Scenario.from_data(
        {
            "schema_version": "2.0",
            "scenario_id": "test-scenario",
            "layout_version": "qoima-72x48-v2",
            "provenance": {
                "kind": "synthetic_fixture",
                "generator_version": "tests",
                "seed": 0,
                "source_notes": "unit test",
                "orders_sha256": ZERO_HASH,
                "receipts_sha256": ZERO_HASH,
            },
            "horizon_s": horizon_s,
            "orders": orders,
            "receipts": receipts or [],
        }
    )


def fixture_order(arrival_s: float = 0, order_id: str = "TEST_001") -> dict[str, Any]:
    return {
        "order_id": order_id,
        "arrival_s": arrival_s,
        "lines": [
            {"sku_id": "FIXTURE_01", "quantity": 1},
            {"sku_id": "FIXTURE_02", "quantity": 1},
        ],
    }


def receipt(index: int, sku_id: str = "FIXTURE_01", quantity: int = 500) -> dict[str, Any]:
    return {
        "receipt_id": f"RCP{index:05d}",
        "arrival_s": (index + 0.5) * 180,
        "sku_id": sku_id,
        "quantity": quantity,
    }


def run_inputs(
    bundle: ContractBundle,
    contracts_dir: Path,
    scen: Scenario,
    **config_updates: Any,
) -> RunInputs:
    base = fixture_inputs(bundle, load_fixture(contracts_dir))
    config = base.config.model_copy(update=config_updates) if config_updates else base.config
    return dataclasses.replace(base, scenario=scen, config=config)


def simulate(inputs: RunInputs) -> tuple[Engine, RunOutcome]:
    engine = Engine(inputs, check_invariants=True)
    return engine, engine.run()
