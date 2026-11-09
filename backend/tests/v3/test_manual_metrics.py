"""Business handoff and paid return use separate, hand-calculated observations."""

from dataclasses import replace

import pytest

from app.v3.execution import ManualEngine
from app.v3.manual_metrics import cycle_statistics, summary
from tests.v3.test_execution_manual import fixture, tick


def test_shipped_cycle_ends_before_paid_worker_return() -> None:
    profile, graph = fixture("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(32), tick(40))
    metrics = summary(profile, outcome)
    horizon = metrics["at_horizon"]
    assert horizon["outbound"]["completed_hus"] == 1
    assert horizon["outbound"]["backlog_hus"] == 0
    assert horizon["outbound"]["completed_units"] == 24
    assert horizon["outbound"]["mean_cycle_s"] == horizon["outbound"]["p95_cycle_s"] == 31
    assert horizon["worker_busy_s"] == 32
    assert horizon["roster_utilization"] == pytest.approx(1 / 24)
    assert horizon["role_pool_utilization"]["ship"] == 1
    assert horizon["operational_status"] == "partial"
    assert metrics["at_end"]["worker_busy_s"] == 33
    assert metrics["at_end"]["operational_status"] == "complete"


def test_business_count_includes_exact_settled_horizon() -> None:
    profile, graph = fixture("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(31), tick(40))
    value = summary(profile, outcome)["at_horizon"]
    assert value["outbound"]["completed_hus"] == 1
    assert value["outbound"]["backlog_hus"] == 0
    assert value["worker_busy_s"] == 31


def test_receipt_cycle_ends_on_putaway_and_return_is_paid() -> None:
    profile, graph = fixture()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(24), tick(40))
    value = summary(profile, outcome)["at_horizon"]
    assert value["inbound"]["completed_hus"] == 1
    assert value["inbound"]["mean_cycle_s"] == 23
    assert value["worker_busy_s"] == 24
    assert value["role_pool_utilization"]["receive"] == 1
    assert value["role_pool_utilization"]["ship"] is None


def test_window_blocked_queue_uses_time_integral() -> None:
    profile, graph = fixture()
    # A10-second intake cannot fit H=11 after the2-second approach. No job admits.
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(11), tick(40))
    value = summary(profile, outcome)["at_horizon"]
    assert value["inbound"]["backlog_hus"] == 1
    assert value["inbound"]["mean_cycle_s"] is None
    assert value["queues"]["port"]["mean_jobs"] == 1
    assert value["queues"]["port"]["job_seconds"] == 11
    assert value["worker_busy_s"] == 0


def test_linear_p95_is_not_nearest_rank() -> None:
    assert cycle_statistics((tick(10), tick(20))) == {
        "mean_cycle_s": 15,
        "p95_cycle_s": 19.5,
    }
    assert cycle_statistics(()) == {"mean_cycle_s": None, "p95_cycle_s": None}


def test_future_planned_motion_is_clipped_to_observed_time() -> None:
    profile, graph = fixture()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(15), tick(18))
    value = summary(profile, outcome)["at_end"]
    assert value["inbound"]["completed_hus"] == 0
    assert value["worker_busy_s"] == 18
    assert value["inbound"]["backlog_hus"] == 1


def test_metrics_reject_wrong_profile_outcome() -> None:
    profile, graph = fixture()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(25), tick(40))
    with pytest.raises(ValueError, match="profile"):
        summary(replace(profile, profile_id="wrong"), outcome)


def test_role_pool_excludes_skilled_workers_not_assigned_to_any_port() -> None:
    profile, graph = fixture("outbound")
    actors = tuple(
        replace(a, skills=frozenset({"ship"})) if a.actor_id == "R02" else a for a in profile.actors
    )
    profile = replace(profile, actors=actors)
    # The declared port still only admits R01; R02's skill creates no port capacity.
    outcome = ManualEngine(profile, graph, check_invariants=True).run(tick(32), tick(40))
    assert summary(profile, outcome)["at_end"]["role_pool_utilization"]["ship"] == 1
