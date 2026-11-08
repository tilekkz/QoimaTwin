"""The new version cannot broaden old APIs, split STANDARD, or promise the same stock twice."""

from dataclasses import replace
from typing import cast

import pytest

from app.v3.light_flow_engine import LightFlowEngine
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockError
from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_stock_fixtures import placements
from tests.v3.test_whole_flow_fixtures import whole_hand_profile
from tests.v3.test_whole_flow_shared_fixtures import standard_receipt_chain


def test_old_light_api_keeps_workstation_custody_policy() -> None:
    with pytest.raises(ValueError, match="handoff owner"):
        LightFlowEngine(whole_hand_profile().receipts.flow, receipt_conveyor())


def test_old_receipt_api_still_rejects_standard_even_with_legacy_actor_owner_types() -> None:
    profile = standard_receipt_chain().receipts
    owners = tuple(
        replace(o, kind="workstation") if o.owner_id in {"actor:P01", "actor:S01"} else o
        for o in profile.flow.owners
    )
    profile = replace(profile, flow=replace(profile.flow, owners=owners))
    with pytest.raises(ValueError, match="receipt execution"):
        ReceiptFlowEngine(profile, receipt_conveyor())


def test_standard_whole_capability_does_not_grant_unit_picking() -> None:
    flow = whole_hand_profile().receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    with pytest.raises(StockError, match="unsupported unit picking class"):
        ledger.pick("forbidden", 0, "HU1", "C1", placements(1, 2, 3))


def test_whole_and_unit_promises_cannot_consume_same_wrapper() -> None:
    profile = whole_hand_profile("SMALL_CARTON")
    receipts = replace(profile.receipts, flow=replace(profile.receipts.flow, orders=hand_orders(1)))
    with pytest.raises(ValueError, match="conflicting"):
        WholeFlowEngine(replace(profile, receipts=receipts), receipt_conveyor())


@pytest.mark.parametrize(
    "fault", ["arrival", "service", "pickup", "capacity", "duplicate", "class"]
)
def test_explicit_whole_types_capacity_and_service_policy_reject(fault: str) -> None:
    profile = whole_hand_profile()
    if fault == "arrival":
        profile = replace(
            profile, orders=(replace(profile.orders[0], arrival_tick=cast(int, True)),)
        )
    elif fault == "service":
        port = replace(profile.ports[0], service_ticks=(("STANDARD_CARTON", cast(int, True)),))
        profile = replace(profile, ports=(port,))
    elif fault == "pickup":
        profile = replace(profile, pickup_tick=cast(int, True))
    elif fault == "capacity":
        owners = tuple(
            replace(o, capacity=2) if o.owner_id == "actor:S02" else o
            for o in profile.receipts.flow.owners
        )
        profile = replace(
            profile,
            receipts=replace(profile.receipts, flow=replace(profile.receipts.flow, owners=owners)),
        )
    elif fault == "duplicate":
        profile = replace(profile, orders=profile.orders * 2)
    else:
        profile = replace(
            profile, ports=(replace(profile.ports[0], service_ticks=(("PALLET", 1),)),)
        )
    with pytest.raises(ValueError):
        WholeFlowEngine(profile, receipt_conveyor())
