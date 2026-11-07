"""Business metrics and open operation intervals preserve observed/expected distinctions."""

import pytest

from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run, validate_manual_run
from tests.v3.test_run_fixtures import manual_profile


def test_manual_wire_reports_business_completion_and_paid_return_separately() -> None:
    profile, graph, document = manual_profile("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(32_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    assert run["source_label"] == "actual_engine_run"
    horizon = run["metrics"]["at_horizon"]
    assert horizon["outbound"]["completed_hus"] == 1
    assert horizon["outbound"]["backlog_hus"] == 0
    assert horizon["outbound"]["mean_cycle_s"] == 31
    assert horizon["worker_busy_s"] == 32
    assert run["metrics"]["at_end"]["worker_busy_s"] == 33
    run["metrics"]["at_end"]["worker_busy_s"] = 999
    with pytest.raises(ValueError, match="metrics"):
        validate_manual_run(run)


def test_cutoff_operation_remains_open_and_checkpoint_keeps_its_identity() -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(15_000_000, 18_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=18_000_000
    )
    action = run["operations"][-1]
    assert action["stage"] == "carry_to_slot"
    assert action["start_tick"] == 17_000_000
    assert action["planned_end_tick"] == 22_000_000
    assert action["observed_end_tick"] == 18_000_000
    assert action["completed"] is False
    assert run["snapshots"][-1]["active_operation_ids"] == [action["operation_id"]]
