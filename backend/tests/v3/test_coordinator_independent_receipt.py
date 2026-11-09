"""Actual receipt creation joins two carts/stations on one shared inventory and clock."""

from collections import Counter
from fractions import Fraction

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.light_flow_models import FlowSnapshot
from tests.v3.test_coordinator_independent_fixtures import separated_arrivals
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def _mixed_packing(snapshot: CoordinatorSnapshot) -> None:
    packing = {row.order_id: row for row in snapshot.packing}
    first, second = packing["O1"], packing["O2"]
    assert (first.actor_id, first.station_id, first.phase) == ("P11", "PK05", "pack")
    assert (second.actor_id, second.station_id, second.phase) == ("P12", "PK06", "clear")
    counts = Counter(row.container_id for row in snapshot.stock.locations)
    assert counts == {"HU1": 18, "HU2": 24, "C1": 3, "P2": 3}
    containers = {row.container_id: row for row in snapshot.stock.containers}
    assert containers["P1"].owner_id == "bench05" and containers["P1"].sealed_for is None
    assert containers["P2"].owner_id == "bench" and containers["P2"].sealed_for == "O2"
    assert containers["C1"].owner_id == "belt:O1"
    assert containers["C2"].owner_id == "belt:O2"
    assert snapshot.balance.gross_mass_kg == Fraction("2.38")


def _after_clear(snapshot: CoordinatorSnapshot) -> None:
    owners = {row.container_id: row.owner_id for row in snapshot.stock.containers}
    assert (owners["C1"], owners["C2"]) == ("empty05", "empties")
    assert (owners["P1"], owners["P2"]) == ("belt:O1", "belt:O2")


def test_receipt_credit_and_paid_return_share_two_cart_station_work() -> None:
    captured: dict[int, CoordinatorSnapshot] = {}

    def capture(snapshot: FlowSnapshot, last_seq: int) -> None:
        assert snapshot.last_seq == last_seq
        if snapshot.tick in {98 * SECOND, 120 * SECOND, 132 * SECOND, 143 * SECOND}:
            assert isinstance(snapshot, CoordinatorSnapshot)
            captured[snapshot.tick] = snapshot

    result = CoordinatorEngine(
        separated_arrivals(receipt=True), receipt_conveyor(), on_tick_settled=capture
    ).run(145 * SECOND, 153 * SECOND)
    carts = {cart.cart_id: cart.order_id for cart in captured[98 * SECOND].carts}
    assert carts == {"CART01": "O1", "CART02": "O2"}
    before, credited = captured[120 * SECOND], captured[132 * SECOND]
    assert "HU2" not in {row.container_id for row in before.stock.containers}
    assert len(before.stock.locations) == 24 and len(credited.stock.locations) == 48
    assert len({row.unit_id for row in credited.stock.locations}) == 48
    putaway = captured[143 * SECOND]
    hu = next(row for row in putaway.stock.containers if row.container_id == "HU2")
    assert hu.owner_id == "new-slot"
    assert putaway.inventory.claims == ()
    _mixed_packing(result.at_horizon)
    receiver = next(row for row in result.at_horizon.workers if row.actor_id == "R01")
    assert receiver.operation is not None and receiver.operation.kind == "receipt_return"
    assert (receiver.operation.start_tick, receiver.operation.planned_end_tick) == (
        143 * SECOND,
        153 * SECOND,
    )
    receipt = result.at_end.receipts[0]
    assert (receipt.credited_tick, receipt.placed_tick, receipt.returned_tick) == (
        132 * SECOND,
        143 * SECOND,
        153 * SECOND,
    )
    assert dict(result.at_end.balance.shipped_units_by_sku) == {}
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 48}
    assert result.at_end.balance.gross_mass_kg == Fraction("2.38")
    _after_clear(result.at_end)
    assert result.status == "partial" and result.constraint_violations == ()
