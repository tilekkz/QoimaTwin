"""Explicit hand custody, staged leases and quantities on the shared calendar."""

from fractions import Fraction as F
from functools import cache

import pytest

from app.v3.light_flow_models import FlowSnapshot
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.receipt_flow_models import ReceiptFlowOutcome, ReceiptFlowSnapshot
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


@cache
def settled_run() -> tuple[ReceiptFlowOutcome, dict[int, ReceiptFlowSnapshot]]:
    observations: dict[int, ReceiptFlowSnapshot] = {}

    def capture(value: FlowSnapshot, last_seq: int) -> None:
        assert isinstance(value, ReceiptFlowSnapshot)
        assert last_seq == value.last_seq
        observations[value.tick] = value

    engine = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor(), on_tick_settled=capture)
    return engine.run(300 * SECOND, 400 * SECOND), observations


@pytest.mark.parametrize(
    ("second", "owner", "claim_id", "whole", "claimed", "reserved_places"),
    [
        (12, "actor:R01", "receipt:R1", True, 24, {"new-slot", "receipt-buffer"}),
        (16, "receipt-buffer", "receipt:R1", True, 24, {"new-slot", "receipt-buffer"}),
        (17, "actor:R01", "receipt:R1", True, 24, {"new-slot"}),
        (23, "new-slot", "pick:O1", False, 3, set()),
    ],
)
def test_settled_custody_and_claim_transition_follow_completed_handling(
    second: int, owner: str, claim_id: str, whole: bool, claimed: int, reserved_places: set[str]
) -> None:
    _, observations = settled_run()
    snapshot = observations[second * SECOND]
    assert next(c for c in snapshot.stock.containers if c.container_id == "HU2").owner_id == owner
    assert snapshot.stock.locations == snapshot.inventory.locations
    assert snapshot.stock.containers == snapshot.inventory.containers
    (claim,) = snapshot.inventory.claims
    assert (claim.claim_id, claim.whole_hu, len(claim.unit_ids)) == (claim_id, whole, claimed)
    expected = {"receipt:worker:R01"} | {"receipt:place:" + p for p in reserved_places}
    if second < 23:
        expected.add("receipt:hu:HU2")
    assert {key for key, _ in snapshot.leases if key.startswith("receipt:")} == expected
    assert snapshot.balance.units_by_sku == (("SKU1", 48),)


def test_initial_tokens_and_completed_pick_are_distinct_from_future_receipt_plan() -> None:
    result, observations = settled_run()
    initial, picked = observations[0], observations[29 * SECOND]
    assert len(initial.inventory.locations) == 24 and not initial.inventory.registered_receipts
    assert {c.container_id for c in initial.stock.containers} == {"HU1", "C1", "P1"}
    assert initial.balance.gross_mass_kg == F(119, 100)
    assert not picked.inventory.claims
    received = {f"HU2:unit:{i:04d}" for i in range(1, 25)}
    assert {u.unit_id for u in picked.inventory.locations if u.unit_id in received} == received
    assert {u.unit_id for u in picked.stock.locations if u.container_id == "C1"} == {
        "HU2:unit:0001",
        "HU2:unit:0002",
        "HU2:unit:0003",
    }
    assert sum(u.container_id == "HU2" for u in picked.stock.locations) == 21
    assert sum(u.container_id == "HU1" for u in picked.stock.locations) == 24
    assert result.at_end.balance.gross_mass_kg == F(213, 100)
    assert result.at_end.balance.onsite_mass_kg == F(79, 40)
    assert result.at_end.balance.shipped_mass_kg == F(31, 200)


def test_clock_watermarks_and_all_actors_preserve_paid_return_after_business_completion() -> None:
    result, observations = settled_run()
    assert result.status == "complete" and result.at_end.tick == 220_170_000
    assert result.at_horizon.tick == 300 * SECOND
    assert result.at_end.orders[0].shipped_tick == 215_170_000
    assert result.at_end.receipts[0].returned_tick == 33 * SECOND
    workers = {w.actor_id: w for w in result.at_end.workers}
    assert len(workers) == 24
    assert [workers[k].paid_ticks for k in ("R01", "P01", "K06", "S01")] == [
        33 * SECOND,
        20 * SECOND,
        8 * SECOND,
        31 * SECOND,
    ]
    assert sum(w.paid_ticks for w in workers.values()) == 92 * SECOND
    assert not result.at_end.leases and not result.at_end.inventory.claims
    assert [event.seq for event in result.events] == list(range(len(result.events)))
    for snapshot in observations.values():
        assert snapshot.last_seq == max(e.seq for e in result.events if e.tick <= snapshot.tick)
    completed = [e for e in result.events if e.kind == "operation_completed"]
    assert all(
        e.operation is not None and e.operation.planned_end_tick == e.tick for e in completed
    )
