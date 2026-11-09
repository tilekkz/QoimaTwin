"""Pre-run source/profile arithmetic; no result or clock is learned from the engine."""

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parents[2]
PROPOSALS = BACKEND / "docs/proposals/adaptive-v3"
SOURCE = BACKEND / "data/v3-proposal/docs/v3/contract-proposals"
NAMES = tuple(
    f"coordinator-{prefix}n4-{side}.example.json"
    for prefix in ("", "tilek-")
    for side in ("baseline", "candidate")
)


def document(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"), parse_float=Fraction)
    return value


@pytest.mark.parametrize("name", NAMES)
def test_mixed_demo_declares_space_for_two_parcels_and_one_intact_hu(name: str) -> None:
    value = document(PROPOSALS / name)
    ports = {row["port_id"]: row["shipped_owner"] for row in value["parcel_ports"]}
    ports.update((row["port_id"], row["shipped_owner"]) for row in value["whole_ports"])
    assignments = {row["order_id"]: row for row in value["unit_assignments"]}
    terminal: dict[str, set[str]] = {}
    for order in value["orders"]:
        owner = ports[assignments[order["order_id"]]["port_id"]]
        terminal.setdefault(owner, set()).add(order["package_id"])
    for order in value["whole_orders"]:
        terminal.setdefault(ports[order["port_id"]], set()).add(order["hu_id"])
    assert terminal == {"shipped": {"P1", "P2", "RECEIVED-STANDARD-1"}}
    owner = next(row for row in value["owners"] if row["owner_id"] == "shipped")
    assert owner["kind"] == "shipped"
    assert owner["capacity"] == 3  # Explicit proposal choice: 2 parcels + 1 intact HU.
    assert len(terminal["shipped"]) <= owner["capacity"]


def test_original_mixed_demo_complete_mass_budget_comes_from_raw_source() -> None:
    value = document(PROPOSALS / NAMES[0])
    catalog = {r["archetype_id"]: r for r in document(SOURCE / "cargo-catalog-v3.json")["records"]}
    initial = document(SOURCE / "baseline-assignment-v3.json")["assignments"]
    initial_mass = sum(
        (Fraction(catalog[r["archetype_id"]]["handling_unit"]["gross_mass_kg"]) for r in initial),
        Fraction(0),
    )
    assert len(initial) == 530
    assert sum(row["quantity_units"] for row in initial) == 12_256
    assert initial_mass == Fraction("9403.85")
    offer = value["receipts"][0]
    assert (offer["sku_id"], offer["quantity_units"]) == ("DEMO_111", 24)
    skus = {r["sku_id"]: r for r in document(SOURCE / "sku-catalog-v3.json")["skus"]}
    assert skus[offer["sku_id"]]["archetype_id"] == "STANDARD_CARTON"
    units = [p["unit_id"] for order in value["orders"] for p in order["package_placements"]]
    assert set(units) == {f"v3:HU:initial:DEMO_001:01:unit:{i:04d}" for i in range(1, 7)}
    assert len(units) == 6
    recipes = {r["recipe_id"]: r for r in value["recipes"]}
    tare = {
        r["container_id"]: Fraction(**recipes[r["recipe_id"]]["tare_kg"])
        for r in value["materials"]
    }
    assert tare == {
        "C1": Fraction(".2"),
        "C2": Fraction(".2"),
        "P1": Fraction(".05"),
        "P2": Fraction(".05"),
    }
    small = catalog["SMALL_CARTON"]["unit"]["gross_mass_kg"]
    standard = catalog["STANDARD_CARTON"]["handling_unit"]["gross_mass_kg"]
    assert small == Fraction(".035") and standard == Fraction("6.35")
    shipped = 6 * small + tare["P1"] + tare["P2"] + standard
    total = initial_mass + sum(tare.values()) + standard
    assert total == Fraction("9410.70")
    assert shipped == Fraction("6.66")
    assert total - shipped == Fraction("9404.04")
    assert 12_256 + 24 - (6 + 24) == 12_250
