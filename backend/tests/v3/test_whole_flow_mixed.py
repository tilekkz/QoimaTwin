"""A unit parcel and original STANDARD compete for the same physical S01 and ledger."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import two_whole_jobs


def test_parcel_waits_for_same_s01_paid_whole_return_without_second_worker_owner() -> None:
    # Whole at160: ship207/return212. Parcel then needs2+1+3+20=26s to238 and5s home243.
    profile = two_whole_jobs()
    flow = replace(profile.receipts.flow, orders=hand_orders(1))
    whole = replace(profile.orders[1], arrival_tick=160 * SECOND)
    profile = replace(
        profile,
        receipts=replace(profile.receipts, flow=flow),
        orders=(whole,),
        ports=(replace(profile.ports[0], shipper_ids=("S01",)),),
    )
    result = WholeFlowEngine(profile, receipt_conveyor()).run(170 * SECOND, 300 * SECOND)
    job = result.at_end.whole_orders[0]
    assert (job.shipped_tick, job.returned_tick) == (207 * SECOND, 212 * SECOND)
    parcel_assignment = next(
        e
        for e in result.events
        if e.kind == "actor_assigned" and e.order_id == "O1" and e.actor_id == "S01"
    )
    assert parcel_assignment.tick == 212 * SECOND
    assert result.at_end.orders[0].shipped_tick == 238 * SECOND
    assert result.at_end.tick == 243 * SECOND
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3, "SKU2": 24}
    assert result.at_end.balance.gross_mass_kg == F("7.54")
    assert result.at_end.balance.shipped_mass_kg == F("6.505")
    assert result.at_end.balance.onsite_mass_kg == F("1.035")
    assert len([o for o in flow.owners if o.owner_id == "actor:S01"]) == 1
    assert not result.at_end.leases and not result.at_end.inventory.claims
