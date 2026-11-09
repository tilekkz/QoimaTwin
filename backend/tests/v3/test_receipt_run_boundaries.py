"""Approach2+service10 credits at12; putaway23/return33 are later business/resource facts."""

from app.v3.receipt_run import build_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def test_service_finishing_after_horizon_does_not_credit_future_receipt() -> None:
    run = build_receipt_run(*sample(11_000_000, 11_000_000))
    state = run["at_end"]["state"]
    assert run["status"] == "partial"
    assert len(state["stock"]["locations"]) == 24
    assert state["inventory"]["registered_receipt_ids"] == []
    assert not any(e["kind"] == "receipt_credited" for e in run["events"])


def test_exact_service_completion_credits_but_does_not_complete_planned_carry() -> None:
    run = build_receipt_run(*sample(12_000_000, 12_000_000))
    state = run["at_horizon"]["state"]
    assert run["status"] == "partial"
    assert len(state["stock"]["locations"]) == 48
    assert state["inventory"]["registered_receipt_ids"] == ["R1"]
    assert state["receipts"][0]["credited_tick"] == 12_000_000
    assert state["receipts"][0]["placed_tick"] is None
    worker = next(w for w in state["workers"] if w["actor_id"] == "R01")
    assert worker["operation"]["start_tick"] == 12_000_000
    assert worker["operation"]["planned_end_tick"] == 15_000_000
    assert state["inventory"]["claims"][0]["whole_hu"] is True
    assert all(e["tick"] <= 12_000_000 for e in run["events"])
