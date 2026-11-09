"""Paired operation forgery and exact handover boundaries retain actual paid custody."""

from pathlib import Path

import pytest

from app.v3.whole_run import build_whole_run, validate_whole_run
from app.v3.whole_transport import read_whole_run, write_whole_run
from tests.v3.test_receipt_flow_fixtures import SECOND
from tests.v3.test_whole_run_fixtures import sample


@pytest.mark.parametrize("field", ["carrying_id", "route"])
def test_matching_started_and_completed_records_still_require_the_declared_plan(field: str) -> None:
    run = build_whole_run(*sample())
    events = [
        event
        for event in run["events"]
        if event["operation"] and event["operation"]["kind"] == "whole_carry_buffer"
    ]
    assert len(events) == 2
    for event in events:
        if field == "route":
            event["operation"]["route"]["arc_ids"] = []
        else:
            event["operation"]["carrying_id"] = None
    with pytest.raises(ValueError, match="directed geometry/service plan"):
        validate_whole_run(run)


def test_horizon_before_ship_and_end_at_ship_keep_paid_return_open(tmp_path: Path) -> None:
    inputs, outcome = sample(False, 46 * SECOND, 47 * SECOND)
    original = build_whole_run(inputs, outcome)
    write_whole_run(original, tmp_path, inputs=inputs.frozen_bytes)
    run = read_whole_run(tmp_path)
    assert run == original and run["status"] == "partial"
    horizon, end = run["at_horizon"]["state"], run["at_end"]["state"]
    assert horizon["whole_orders"][0]["shipped_tick"] is None
    assert end["whole_orders"][0]["shipped_tick"] == 47 * SECOND
    assert end["whole_orders"][0]["returned_tick"] is None
    assert end["inventory"]["claims"] == []
    assert end["leases"] == [["whole:worker:S01", "W1"]]
    worker = next(w for w in end["workers"] if w["actor_id"] == "S01")
    assert worker["operation"]["kind"] == "whole_return"
    assert worker["operation"]["planned_end_tick"] == 52 * SECOND
    assert worker["paid_ticks"] == 47 * SECOND
    assert not any(e["kind"] == "whole_returned" for e in run["events"])
    assert run["metrics"]["at_horizon"]["whole"]["completed_units"] == 0
    assert run["metrics"]["at_end"]["whole"]["completed_units"] == 24
    assert run["metrics"]["at_end"]["whole"]["pending_return"] == 1
