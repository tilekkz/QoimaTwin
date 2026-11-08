"""Explicit24-unit mass and finite material-pool hand arithmetic; no new DES."""

from dataclasses import replace

import pytest

from app.v3.coordinator_metrics_inventory import inventory
from app.v3.coordinator_metrics_materials import materials
from app.v3.light_flow_models import FlowEvent, FlowOrderView
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockOwner
from app.v3.stock_receipts import ReceiptDefinition
from tests.v3.test_coordinator_kpi_fixtures import S, outcome, point, profile
from tests.v3.test_light_flow_fixtures import hand_orders


def test_initial_mass_and_owner_totals_include_empty_material_tare_once() -> None:
    value = profile()
    snapshot = point(value, 10 * S)
    result = inventory(value, outcome(snapshot), snapshot)
    assert result["gross_mass_kg"] == {"numerator": 36, "denominator": 25}  # .94+.4+.1
    assert result["onsite_units"] == 24
    assert result["zones"]["available"] is False  # Analytical fixture has no source zones.


def test_material_pool_integral_uses_admission_before_physical_transfer() -> None:
    value = profile()
    flow = replace(value.world.receipts.flow, orders=(hand_orders(1)[0],))
    value = replace(
        value, world=replace(value.world, receipts=replace(value.world.receipts, flow=flow))
    )
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    delta = ledger.relocate("take", 0, "C1", "actor:P01")
    snapshot = replace(
        point(value, 10 * S, ledger),
        orders=(FlowOrderView("O1", "picking", 4 * S, None),),
        last_seq=0,
    )
    event = FlowEvent(0, 5 * S, "carrier_taken", "O1", delta=delta)
    rows = materials(value, outcome(snapshot, (event,)), snapshot)
    pool = next(row for row in rows if row["owner_id"] == "carrier-pool")
    assert pool["empty_unbound_container_ticks"] == 14 * S  # 2*4 + 1*6
    assert pool["current_empty_unbound_containers"] == 1
    assert pool["zero_empty_unbound_ticks"] == 0


def test_idle_pool_integral_has_no_default_tote_population() -> None:
    value = profile()
    snapshot = point(value, 10 * S)
    rows = materials(value, outcome(snapshot), snapshot)
    pool = next(row for row in rows if row["owner_id"] == "carrier-pool")
    assert pool["empty_unbound_container_ticks"] == 20 * S
    assert pool["capacity"] == 2
    rack = next(row for row in rows if row["owner_id"] == "empties")
    assert rack["free_place_ticks"] == 20 * S
    assert rack["current_free_places"] == 2
    assert rack["current_empty_unbound_containers"] == 0


def test_same_quantity_under_another_sku_cannot_impersonate_observed_accounting() -> None:
    value = profile()
    snapshot = point(value, 0)
    snapshot = replace(
        snapshot,
        balance=replace(
            snapshot.balance,
            units_by_sku=(("OTHER", 24),),
            onsite_units_by_sku=(("OTHER", 24),),
        ),
    )
    with pytest.raises(ValueError, match="SKU"):
        inventory(value, outcome(snapshot), snapshot)


def test_both_assigned_carriers_make_empty_unbound_pool_zero_without_physical_take() -> None:
    value = profile()
    flow = replace(value.world.receipts.flow, orders=hand_orders(2))
    value = replace(
        value, world=replace(value.world, receipts=replace(value.world.receipts, flow=flow))
    )
    orders = tuple(FlowOrderView(f"O{i}", "picking", 4 * S, None) for i in (1, 2))
    snapshot = replace(point(value, 10 * S), orders=orders)
    pool = next(
        row
        for row in materials(value, outcome(snapshot), snapshot)
        if row["owner_id"] == "carrier-pool"
    )
    assert pool["container_ticks"] == 20 * S
    assert pool["empty_unbound_container_ticks"] == 8 * S
    assert pool["zero_empty_unbound_ticks"] == 6 * S


def test_material_snapshot_without_its_transfer_journal_is_rejected() -> None:
    value = profile()
    flow = value.world.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    ledger.relocate("take", 0, "C1", "actor:P01")
    snapshot = point(value, 10 * S, ledger)
    with pytest.raises(ValueError, match="journal"):
        materials(value, outcome(snapshot), snapshot)


def test_receipt_creates_units_only_at_actual_credit_including_boundary() -> None:
    value = profile()
    flow = value.world.receipts.flow
    flow = replace(flow, owners=(*flow.owners, StockOwner("receive", "buffer", 1)))
    value = replace(
        value, world=replace(value.world, receipts=replace(value.world.receipts, flow=flow))
    )
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    before = point(value, 12 * S - 1, ledger)
    definition = ReceiptDefinition("R1", "HU2", "SKU1", "LOT2", 24)
    delta = ledger.receive_hu("credit", 0, definition, "receive")
    events = (FlowEvent(0, 12 * S, "receipt_credited", "R1", delta=delta),)
    after = point(value, 12 * S, ledger)
    assert inventory(value, outcome(before, events), before)["onsite_units"] == 24
    result = inventory(value, outcome(after, events), after)
    assert result["onsite_units"] == 48
    assert result["gross_mass_kg"] == {"numerator": 119, "denominator": 50}  # 1.44+.94
