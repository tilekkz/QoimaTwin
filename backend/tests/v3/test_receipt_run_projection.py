"""24 existing units plus24 credited units minus3 shipped is45 onsite, never72."""

from app.v3.receipt_run import build_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def test_future_receipt_descriptors_do_not_credit_initial_stock() -> None:
    run = build_receipt_run(*sample())
    initial, end = run["checkpoints"][0]["state"], run["at_end"]["state"]
    assert len(run["catalog"]["initial_units"]) == 24
    assert len(run["catalog"]["declared_receipts"][0]["units"]) == 24
    assert len(initial["stock"]["locations"]) == 24
    assert initial["inventory"]["registered_receipt_ids"] == []
    assert len(end["stock"]["locations"]) == 48
    assert end["balance"]["onsite_units_by_sku"] == [["SKU1", 45]]
    assert end["balance"]["shipped_units_by_sku"] == [["SKU1", 3]]
    assert end["balance"]["onsite_mass_kg"] == {"numerator": 79, "denominator": 40}
    assert end["inventory"]["claims"] == [] and end["leases"] == []
    assert run["observed_until_tick"] == 220_170_000 and run["status"] == "complete"


def test_creation_and_claim_events_preserve_actual_service_completion() -> None:
    run = build_receipt_run(*sample())
    credit = next(e for e in run["events"] if e["kind"] == "receipt_credited")
    assert credit["tick"] == 12_000_000
    assert credit["delta"]["before"] == [] and len(credit["delta"]["created_tokens"]) == 24
    assert credit["delta"]["receipt"]["receipt_id"] == "R1"
    assert [e["seq"] for e in run["events"]] == list(range(len(run["events"])))
    assert any(e["inventory_claim"] for e in run["events"])
    assert any(e["released_claim_id"] for e in run["events"])
    assert len(run["at_end"]["state"]["workers"]) == 24
