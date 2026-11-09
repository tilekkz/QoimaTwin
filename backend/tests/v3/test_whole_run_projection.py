"""Intact HU business handover and paid return remain separate published observations."""

from app.v3.flow_profile_wire import record
from app.v3.whole_native_decode import decode_outcome
from app.v3.whole_run import build_whole_run
from tests.v3.test_receipt_flow_fixtures import SECOND
from tests.v3.test_whole_run_fixtures import sample


def test_original_standard_handover_47_return_52_and_one_worker_exposure() -> None:
    inputs, outcome = sample()
    run = build_whole_run(inputs, outcome)
    assert run["schema_id"] == "qoima.connected-manual-whole-run.v3-proposal"
    row = run["at_end"]["state"]["whole_orders"][0]
    assert (row["shipped_tick"], row["returned_tick"]) == (47 * SECOND, 52 * SECOND)
    counts = run["metrics"]["at_end"]
    assert counts["whole"]["completed_units"] == 24
    assert counts["unit"]["completed_units"] == 0
    assert counts["labor"]["paid_ticks"] == 52 * SECOND
    assert row["port_reservation_ticks"] == 40 * SECOND
    assert row["port_service_ticks"] == 35 * SECOND
    assert run["status"] == "complete"


def test_future_standard_ancestry_and_putaway_then_whole_journal() -> None:
    inputs, outcome = sample(True)
    run = build_whole_run(inputs, outcome)
    receipt = run["at_end"]["state"]["receipts"][0]
    assert [receipt[k] for k in ("credited_tick", "placed_tick", "returned_tick")] == [
        20 * SECOND,
        31 * SECOND,
        41 * SECOND,
    ]
    whole = run["at_end"]["state"]["whole_orders"][0]
    assert (whole["shipped_tick"], whole["returned_tick"]) == (78 * SECOND, 83 * SECOND)
    assert len(run["catalog"]["initial_units"]) == 24
    assert len(run["at_end"]["state"]["stock"]["locations"]) == 48
    assert run["metrics"]["at_end"]["labor"]["paid_ticks"] == 93 * SECOND
    assert record(decode_outcome(record(outcome))) == record(outcome)


def test_business_complete_before_cap_does_not_erase_paid_return() -> None:
    inputs, outcome = sample(False, 48 * SECOND, 52 * SECOND - 1)
    run = build_whole_run(inputs, outcome)
    assert run["status"] == "partial"
    assert run["metrics"]["at_end"]["whole"]["backlog_orders"] == 0
    assert run["metrics"]["at_end"]["whole"]["pending_return"] == 1
    assert run["at_end"]["state"]["whole_orders"][0]["returned_tick"] is None
