"""Full immutable input projection, separate from any future paired-comparison projection."""

from typing import Any

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.flow_profile_wire import materialized_record, record
from app.v3.stock_ledger import StockLedger
from app.v3.whole_profile_geometry import ROUTE_POLICY


def materialized(profile: CoordinatorProfile, ledger: StockLedger) -> dict[str, Any]:
    world, receipts = profile.world, profile.world.receipts
    return {
        **materialized_record(receipts.flow, ledger),
        "initial_inventory": record(ledger.inventory_snapshot()),
        "route_policy": ROUTE_POLICY,
        "receipt_process": {
            "ports": record(receipts.ports),
            "places": record(receipts.places),
            "offers": record(receipts.receipts),
            "pickup_tick": receipts.pickup_tick,
            "place_tick": receipts.place_tick,
        },
        "whole_process": {
            "ports": record(world.ports),
            "places": record(world.places),
            "orders": record(world.orders),
            "pickup_tick": world.pickup_tick,
            "place_tick": world.place_tick,
        },
        "coordinator": {
            "stations": record(profile.stations),
            "role_intents": record(profile.intents),
            "unit_resources": record(profile.unit_resources),
        },
    }
