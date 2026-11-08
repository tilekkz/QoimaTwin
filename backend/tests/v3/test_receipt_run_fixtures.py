"""Hand receipt publication inputs; expected arithmetic is in the runtime fixture document."""

from dataclasses import dataclass, replace
from functools import cache

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.flow_profile_wire import materialized_record, record
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.receipt_flow_models import ReceiptFlowOutcome, ReceiptFlowProfile
from app.v3.receipt_flow_validate import validate_receipt_flow
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor, receipt_hand_profile


@dataclass(frozen=True)
class HandInputs:
    profile: ReceiptFlowProfile
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes
    input_hash: str


@cache
def sample(
    horizon: int = 300_000_000, end: int = 400_000_000, arrival: int = 0
) -> tuple[HandInputs, ReceiptFlowOutcome]:
    profile, conveyor = receipt_hand_profile(), receipt_conveyor()
    profile = replace(profile, receipts=(replace(profile.receipts[0], arrival_tick=arrival),))
    ledger = validate_receipt_flow(profile, conveyor)
    frozen = {
        "compiler_version": "qoima-receipt-hand-fixture-0.1.0",
        "scope": "explicit_hand_connected_receipt_small_fixture",
        "choices": {"horizon_tick": horizon, "end_tick": end},
        **materialized_record(profile.flow, ledger),
        "initial_inventory": record(ledger.inventory_snapshot()),
        "receipt_process": {
            "ports": record(profile.ports),
            "places": record(profile.places),
            "offers": record(profile.receipts),
            "pickup_tick": profile.pickup_tick,
            "place_tick": profile.place_tick,
            "route_policy": "explicit-hand-receipt-fixture-v1",
        },
    }
    inputs = HandInputs(profile, horizon, end, canonical_bytes(frozen), sha256_hex(frozen))
    return inputs, ReceiptFlowEngine(profile, conveyor).run(horizon, end)
