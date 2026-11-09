"""Small explicit planning inputs on the full layout (hand-checked, never engine output).

Slot costs and swap routes used by the planning tests were derived by hand from
contracts/layout.example.json (independent oracle, see docs/adr/0016):

- aisle Ai is at x = 10 + 4.5(i-1); aisle nodes every 2 m at z = 14..42; cross-aisles at
  z = 14, 28, 42; homes I01/I02/I03 hang 2 m below A01/A05/A09 at z = 14;
- N_REL_BUFFER has one edge, 6.5 m, to N_A12_Z42;
- mean home round trip of a ground slot = (2/3) * sum of the three home distances.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from app.contracts.assignment import Assignment
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.planning import PlanningInputs

CHEAP = "S_A01_B01_L_01"  # service N_A01_Z16, mean round trip 44 m
DEAR = "S_A12_B09_R_01"  # service N_A12_Z34, mean round trip 107 m
SWAP_ROUTE_M = Fraction(336)  # I02,A,buffer,B,A,buffer,B,I02 for CHEAP <-> DEAR
SWAP_LABOR_S = Fraction(328)  # 336 / 1.2 + 6 * 8
RESERVE_SLOT = "S_A01_B01_L_02"


def assignment(placement: dict[str, str], *, reserve: bool = True) -> Assignment:
    """slot -> SKU, 2000 units on each ground slot, plus one 500-unit reserve lot."""
    lots: list[dict[str, Any]] = [
        {"lot_id": f"GROUND_{sku}", "sku_id": sku, "slot_id": slot, "quantity": 2000}
        for slot, sku in sorted(placement.items())
    ]
    if reserve:
        first_sku = sorted(placement.values())[0]
        lots.append(
            {"lot_id": "RESERVE_1", "sku_id": first_sku, "slot_id": RESERVE_SLOT, "quantity": 500}
        )
    return Assignment.from_data(
        {
            "schema_version": "2.0",
            "layout_version": "qoima-72x48-v2",
            "assignment_id": "planning-test",
            "provenance": {"kind": "test", "note": "hand-built"},
            "active_assignment": placement,
            "initial_lots": lots,
        }
    )


def two_sku_inputs(
    layout: Layout,
    config: SimulationConfig,
    *,
    expected: dict[str, float],
    training: dict[str, float] | None = None,
    hot_on_dear: bool = True,
) -> PlanningInputs:
    """SKU_X on CHEAP and SKU_Y on DEAR (or the reverse when hot_on_dear is False)."""
    placement = {CHEAP: "SKU_X", DEAR: "SKU_Y"} if hot_on_dear else {CHEAP: "SKU_Y", DEAR: "SKU_X"}
    return PlanningInputs(
        layout=layout,
        config=config,
        baseline_assignment=assignment(placement),
        training_visits=training or {"SKU_X": 1.0, "SKU_Y": 1.0},
        expected_visits=expected,
        forecast_id="forecast-test",
    )


def forecast_semantics(visits_y: float = 10.0, model: str = "mean28") -> dict[str, Any]:
    return {
        "protocol": "qoima-forecast-temporal-1",
        "model": model,
        "history_hash": "a" * 64,
        "cutoff": "2026-11-08",
        "test_day": "2026-11-09",
        "predictions": {"visits_by_sku": {"SKU_X": 0.0, "SKU_Y": visits_y}},
        "training_visits_by_sku": {"SKU_X": 1.0, "SKU_Y": 1.0},
        "validation": {"wape": 0.25, "absolute_error": 5.0, "actual_visits": 20.0},
        "synthetic_training": True,
        "parameters": {"window": 28},
        "features": ["mean28"],
        "full_day_s": 28800,
    }
