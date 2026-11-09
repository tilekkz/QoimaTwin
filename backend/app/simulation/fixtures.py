"""Build run inputs for the analytical fixture (contracts/analytical_fixture.json, ADR 0009 A27).

The fixture file is a wrapper, not a schema-valid scenario. This module turns it into a valid
`Scenario` plus an `Assignment` with only the fixture SKUs placed, so the engine runs it unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.contracts.assignment import Assignment
from app.contracts.loader import ContractBundle
from app.contracts.scenario import Scenario
from app.simulation.context import RunInputs

FIXTURE_FILE = "analytical_fixture.json"
FIXTURE_HORIZON_S = 3600


def _sha256(data: Any) -> str:
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_fixture(contracts_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((contracts_dir / FIXTURE_FILE).read_text(encoding="utf-8"))
    return data


def fixture_inputs(bundle: ContractBundle, fixture: dict[str, Any]) -> RunInputs:
    spec = fixture["scenario"]
    orders = spec["arrivals"]
    scenario = Scenario.from_data(
        {
            "schema_version": "2.0",
            "scenario_id": spec["scenario_id"],
            "layout_version": fixture["layout_version"],
            "provenance": {
                "kind": "synthetic_fixture",
                "generator_version": "analytical-fixture-adapter-1",
                "seed": 0,
                "source_notes": "contracts/analytical_fixture.json",
                "orders_sha256": _sha256(orders),
                "receipts_sha256": _sha256(spec["receipts"]),
            },
            "horizon_s": FIXTURE_HORIZON_S,
            "orders": orders,
            "receipts": spec["receipts"],
        }
    )
    placement = dict(spec["assignment_override"])
    units = bundle.config.ground_units_per_sku
    assignment = Assignment.from_data(
        {
            "schema_version": "2.0",
            "layout_version": fixture["layout_version"],
            "assignment_id": f"{spec['scenario_id']}-assignment",
            "provenance": {"kind": "synthetic_fixture", "note": "analytical fixture override"},
            "active_assignment": placement,
            "initial_lots": [
                {"lot_id": f"GROUND_{sku}", "sku_id": sku, "slot_id": slot, "quantity": units}
                for slot, sku in sorted(placement.items())
            ],
        }
    )
    return RunInputs(
        layout=bundle.layout,
        config=bundle.config,
        actors=bundle.actors,
        assignment=assignment,
        scenario=scenario,
        experiment_type="fixture",
    )
