"""Mandatory initial warehouse scale, directly from acceptance specification section1."""

from pathlib import Path

from app.contracts.assignment import Assignment
from app.contracts.loader import ContractBundle
from app.inventory.ledger import LocKind
from app.simulation.context import RunInputs, build_ledger
from tests.builders import scenario


def test_P0_initial_building_addresses_and_inventory(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    layout = bundle.layout
    assignment = Assignment.from_json_text((contracts_dir / "assignment.example.json").read_bytes())
    occupied = {lot.slot_id for lot in assignment.initial_lots}
    assert layout.bounds.max[0] - layout.bounds.min[0] == 72
    assert layout.bounds.max[2] - layout.bounds.min[2] == 48
    assert len(occupied) == 600
    assert len(layout.slots) - len(occupied) == 264
    inputs = RunInputs(layout, bundle.config, bundle.actors, assignment, scenario([]))
    ledger, active = build_ledger(inputs)
    assert len(active) == 200
    assert len(assignment.empty_pickfaces) == 88
    assert sum(ledger.buckets(sku)[LocKind.PICKFACE] for sku in ledger.skus()) == 400_000
    assert sum(ledger.buckets(sku)[LocKind.RESERVE_SLOT] for sku in ledger.skus()) == 200_000
    assert ledger.check_conservation() == []
