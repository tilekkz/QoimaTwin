"""Pure accounting oracle: an empty-rack return never replenishes the carrier pool."""

from dataclasses import replace

from app.v3.coordinator_metrics_materials import materials
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.light_flow_models import FlowEvent, FlowOrderView
from app.v3.stock_ledger import StockLedger
from tests.v3.test_coordinator_kpi_fixtures import S, outcome, point, profile
from tests.v3.test_light_flow_fixtures import hand_orders


def _profile() -> CoordinatorProfile:
    value = profile()
    receipts = value.world.receipts
    flow = replace(receipts.flow, orders=hand_orders(2))
    return replace(value, world=replace(value.world, receipts=replace(receipts, flow=flow)))


def _journal(value: CoordinatorProfile) -> tuple[StockLedger, tuple[FlowEvent, ...]]:
    flow = value.world.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    order = flow.orders[0]
    changes = (
        (5, "carrier_attached", ledger.relocate("take", 0, "C1", "actor:P01")),
        (6, "picked", ledger.pick("pick", 1, "HU1", "C1", order.carrier_placements)),
        (7, "package_prepared", ledger.relocate("bench", 2, "P1", "bench")),
        (8, "packed", ledger.pack("pack", 3, "C1", "P1", order.package_placements, order_id="O1")),
        (8, "empty_carrier_cleared", ledger.relocate("rack", 4, "C1", "empties")),
        (9, "shipped", ledger.ship("ship", 5, "P1", "shipped")),
    )
    return ledger, tuple(
        FlowEvent(seq, tick * S, kind, "O1", delta=delta)
        for seq, (tick, kind, delta) in enumerate(changes)
    )


def test_same_tick_second_binding_and_rack_return_do_not_create_pool_supply() -> None:
    value = _profile()
    ledger, events = _journal(value)
    captured = replace(
        point(value, 10 * S, ledger),
        orders=(
            FlowOrderView("O1", "shipped", 4 * S, 9 * S),
            FlowOrderView("O2", "active", 8 * S, None),
        ),
        last_seq=len(events) - 1,
    )
    rows = {row["owner_id"]: row for row in materials(value, outcome(captured, events), captured)}
    pool, rack = rows["carrier-pool"], rows["empties"]
    # Physical pool: 2*5 + 1*5. Available: 2*4 + 1*4 + 0*2.
    assert pool["container_ticks"] == 15 * S
    assert pool["empty_unbound_container_ticks"] == 12 * S
    assert pool["zero_empty_unbound_ticks"] == 2 * S
    assert pool["current_containers"] == 1
    assert pool["current_empty_unbound_containers"] == 0
    assert pool["free_place_ticks"] == 5 * S
    # C1 enters the rack at8, stays bound until shipment9, then is available HERE.
    assert rack["container_ticks"] == 2 * S
    assert rack["empty_unbound_container_ticks"] == S
    assert rack["zero_empty_unbound_ticks"] == 9 * S
    assert rack["current_containers"] == rack["current_empty_unbound_containers"] == 1
    assert rack["free_place_ticks"] == 18 * S
