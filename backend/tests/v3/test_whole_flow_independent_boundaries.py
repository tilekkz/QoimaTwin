"""Hand graph fixes STD putaway31, shipment78 and paid home return83."""

from dataclasses import replace
from fractions import Fraction

import pytest

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import standard_receipt_chain, two_whole_jobs


@pytest.mark.parametrize("horizon,admitted", [(31 * SECOND, False), (31 * SECOND + 1, True)])
def test_exact_putaway_horizon_does_not_admit_a_new_whole_job(horizon: int, admitted: bool) -> None:
    engine = WholeFlowEngine(standard_receipt_chain(), receipt_conveyor())
    result = engine.run(horizon, 100 * SECOND)
    assert result.at_end.receipts[0].placed_tick == 31 * SECOND
    assert result.at_end.receipts[0].returned_tick == 41 * SECOND
    job = result.at_end.whole_orders[0]
    assert job.admitted_tick == (31 * SECOND if admitted else None)
    assert job.shipped_tick == (78 * SECOND if admitted else None)
    assert job.returned_tick == (83 * SECOND if admitted else None)
    assert result.status == ("complete" if admitted else "partial")
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 48}
    assert result.at_end.balance.onsite_mass_kg + result.at_end.balance.shipped_mass_kg == Fraction(
        "12.95"
    )
    assert not result.at_end.inventory.claims


def test_cap_after_intact_shipment_preserves_the_last_microsecond_of_paid_return() -> None:
    engine = WholeFlowEngine(standard_receipt_chain(), receipt_conveyor())
    result = engine.run(40 * SECOND, 83 * SECOND - 1)
    job = result.at_end.whole_orders[0]
    assert job.shipped_tick == 78 * SECOND and job.returned_tick is None
    assert result.status == "partial" and result.at_end.tick == 83 * SECOND - 1
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert result.at_end.balance.shipped_mass_kg == Fraction("6.35")
    assert result.at_end.balance.onsite_mass_kg == Fraction("6.60")
    assert not result.at_end.inventory.claims
    assert dict(result.at_end.leases) == {"whole:worker:S01": "W1"}
    worker = next(w for w in result.at_end.workers if w.actor_id == "S01")
    assert worker.operation is not None and worker.operation.carrying_id is None
    assert (worker.operation.start_tick, worker.operation.planned_end_tick) == (
        78 * SECOND,
        83 * SECOND,
    )
    assert not any(e.kind == "whole_returned" for e in result.events)


def test_full_shipped_owner_keeps_second_wrapper_in_buffer_without_port_reservation() -> None:
    profile = two_whole_jobs()
    flow = profile.receipts.flow
    owners = tuple(replace(o, capacity=1) if o.owner_id == "shipped" else o for o in flow.owners)
    profile = replace(
        profile, receipts=replace(profile.receipts, flow=replace(flow, owners=owners))
    )
    engine = WholeFlowEngine(profile, receipt_conveyor())
    result = engine.run(20 * SECOND, 80 * SECOND)
    first, second = result.at_end.whole_orders
    assert (first.shipped_tick, first.returned_tick) == (37 * SECOND, 42 * SECOND)
    assert second.wait_reason == "shipped_capacity" and second.buffer_picked_tick is None
    assert second.port_reserved_tick is None and second.port_reservation_ticks == 0
    assert second.paid_exposure_ticks == 80 * SECOND and second.shipped_tick is None
    assert result.status == "partial"
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert dict(result.at_end.balance.onsite_units_by_sku) == {"SKU2": 24}
    assert result.at_end.balance.onsite_mass_kg == Fraction("6.60")
    assert result.at_end.balance.shipped_mass_kg == Fraction(".94")
    assert {c.claim_id for c in result.at_end.inventory.claims} == {"whole:W2"}
    assert not any(
        k.startswith("port:") or k.startswith("whole:shipped:") for k, _ in result.at_end.leases
    )
    assert engine.ledger.contents("HU3").container.owner_id == second.buffer_owner_id
    assert len(engine.ledger.contents("HU3").units) == 24
