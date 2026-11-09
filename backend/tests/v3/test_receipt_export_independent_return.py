"""Putaway23 is business completion; receiver's ten-second return ends at33."""

from app.v3.receipt_run import build_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def test_h30_keeps_paid_receiver_return_after_putaway_and_unit_pick() -> None:
    run = build_receipt_run(*sample(30_000_000, 30_000_000))
    state = run["at_end"]["state"]
    receipt = state["receipts"][0]
    assert run["status"] == "partial"
    assert receipt["credited_tick"] == 12_000_000
    assert receipt["placed_tick"] == 23_000_000 and receipt["returned_tick"] is None
    assert receipt["paid_exposure_ticks"] == 30_000_000
    assert state["balance"]["onsite_units_by_sku"] == [["SKU1", 48]]
    assert state["balance"]["onsite_mass_kg"] == {"numerator": 213, "denominator": 100}
    assert state["inventory"]["claims"] == []
    resources = {row[0] for row in state["leases"] if row[0].startswith("receipt:")}
    assert resources == {"receipt:worker:R01"}
    receiver = next(w for w in state["workers"] if w["actor_id"] == "R01")
    assert receiver["operation"]["start_tick"] == 23_000_000
    assert receiver["operation"]["planned_end_tick"] == 33_000_000
    assert all(e["tick"] <= 30_000_000 for e in run["events"])
    assert run["capabilities"]["frontend_adapter"] is False
    assert run["capabilities"]["full_v3"] is False
