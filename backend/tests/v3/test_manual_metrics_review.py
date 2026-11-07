"""Independent metrics arithmetic; no expected value is obtained from engine output."""

from dataclasses import replace

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_types import InitialPlacement, TimedJob
from app.v3.manual_metrics import summary
from tests.v3.test_manual_acceptance_chain import chain_fixture
from tests.v3.test_manual_acceptance_fixtures import ManualFixture, business_fixture, fixture, ticks


def two_outbounds() -> ManualFixture:
    data = business_fixture("outbound")
    profile = data.profile
    actors = tuple(
        replace(actor, skills=frozenset({"ship"})) if actor.actor_id == "R02" else actor
        for actor in profile.actors
    )
    second = replace(profile.handling_units[0], hu_id="HU2")
    slot = replace(profile.slots[0], place_id="slot2")
    port = profile.ports[0]
    port = replace(
        port,
        buffer_places=(*port.buffer_places, replace(port.buffer_places[0], place_id="buffer2")),
    )
    profile = replace(
        profile,
        actors=actors,
        ports=(port,),
        slots=(*profile.slots, slot),
        handling_units=(*profile.handling_units, second),
        initial_placements=(*profile.initial_placements, InitialPlacement("HU2", "slot2")),
        jobs=(*profile.jobs, TimedJob("J2", 0, "outbound", "HU2", "port1", "slot2")),
    )
    return replace(data, profile=profile)


def test_three_port_person_seconds_and_queue_arithmetic() -> None:
    data = fixture()
    outcome = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(25), ticks(40)
    )
    metrics = summary(data.profile, outcome)
    horizon, end = metrics["at_horizon"], metrics["at_end"]
    assert horizon["worker_busy_s"] == 40  # R01[0,25) plus R02[0,15).
    assert end["worker_busy_s"] == 45  # 13+15+17.
    assert horizon["role_busy_s"] == {"receive": 40, "ship": 0}
    assert horizon["role_pool_utilization"]["receive"] == pytest.approx(40 / 50)
    assert horizon["roster_utilization"] == pytest.approx(40 / (25 * 24))
    assert horizon["queues"]["port3"]["job_seconds"] == 13
    assert horizon["queues"]["port3"]["mean_jobs"] == pytest.approx(13 / 25)
    assert end["queues"]["port3"]["mean_jobs"] == pytest.approx(13 / 30)
    assert horizon["inbound"]["mean_cycle_s"] == pytest.approx(43 / 3)
    assert horizon["inbound"]["p95_cycle_s"] == pytest.approx(22.6)


def test_horizon_later_than_completion_changes_denominator_not_labor() -> None:
    data = fixture((1, 1))
    outcome = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(20), ticks(25)
    )
    metrics = summary(data.profile, outcome)
    horizon, end = metrics["at_horizon"], metrics["at_end"]
    assert horizon["time_s"] == 20 and end["time_s"] == 19
    assert horizon["worker_busy_s"] == end["worker_busy_s"] == 26
    assert horizon["role_pool_utilization"]["receive"] == pytest.approx(26 / 40)
    assert end["role_pool_utilization"]["receive"] == pytest.approx(26 / 38)
    assert horizon["queues"]["port1"]["job_seconds"] == end["queues"]["port1"]["job_seconds"] == 6
    assert horizon["queues"]["port1"]["mean_jobs"] == pytest.approx(6 / 20)
    assert end["queues"]["port1"]["mean_jobs"] == pytest.approx(6 / 19)
    assert end["inbound"]["mean_cycle_s"] == 12
    assert end["inbound"]["p95_cycle_s"] == pytest.approx(14.7)


def test_dual_skill_workers_partition_role_seconds_without_double_counting() -> None:
    data = chain_fixture()
    outcome = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(26), ticks(35)
    )
    metrics = summary(data.profile, outcome)
    horizon, end = metrics["at_horizon"], metrics["at_end"]
    assert horizon["role_busy_s"] == {"receive": 13, "ship": 17}
    assert end["role_busy_s"] == {"receive": 13, "ship": 19}
    assert horizon["worker_busy_s"] == sum(horizon["role_busy_s"].values()) == 30
    assert end["worker_busy_s"] == sum(end["role_busy_s"].values()) == 32
    assert horizon["role_pool_utilization"] == {"receive": 13 / 52, "ship": 17 / 52}
    assert horizon["queues"]["port2"]["job_seconds"] == 9
    assert horizon["outbound"]["completed_hus"] == 1
    assert horizon["operational_status"] == "partial"


def test_two_shipping_jobs_wait_on_one_bay_and_finish_inclusively() -> None:
    data = two_outbounds()
    outcome = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(45), ticks(50)
    )
    metrics = summary(data.profile, outcome)
    horizon, end = metrics["at_horizon"], metrics["at_end"]
    assert horizon["outbound"]["completed_hus"] == 2
    assert horizon["outbound"]["backlog_hus"] == 0
    assert horizon["outbound"]["mean_cycle_s"] == 38  # (31+45)/2.
    assert horizon["outbound"]["p95_cycle_s"] == pytest.approx(44.3)
    assert horizon["worker_busy_s"] == 78  # 33+45, includes blocked-held worker.
    assert end["worker_busy_s"] == 80  # 33+47.
    assert horizon["queues"]["port1"]["job_seconds"] == 14  # Second waits[17,31).
    assert horizon["queues"]["port1"]["wait_seconds_by_reason"]["port_busy"] == 14
    assert horizon["queues"]["port1"]["mean_jobs"] == pytest.approx(14 / 45)
    assert end["time_s"] == 47


def test_active_wait_reason_changes_integrate_to_end_cap() -> None:
    data = two_outbounds()
    outcome = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(35), ticks(50)
    )
    metrics = summary(data.profile, outcome)
    horizon, end = metrics["at_horizon"], metrics["at_end"]
    assert horizon["queues"]["port1"]["job_seconds"] == 18  # [17,35).
    assert end["queues"]["port1"]["job_seconds"] == 33  # [17,50).
    reasons = end["queues"]["port1"]["wait_seconds_by_reason"]
    assert reasons["port_busy"] == 14 and reasons["port_window"] == 19
    assert horizon["worker_busy_s"] == 68  # 33+35.
    assert end["worker_busy_s"] == 83  # 33+50.
    assert horizon["outbound"]["completed_hus"] == end["outbound"]["completed_hus"] == 1
    assert end["outbound"]["backlog_hus"] == 1
    assert end["operational_status"] == "partial"


def test_exact_handover_counts_and_half_open_return_labor_are_separate() -> None:
    data = business_fixture("outbound")
    outcome = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(31), ticks(40)
    )
    metrics = summary(data.profile, outcome)
    horizon = metrics["at_horizon"]
    assert horizon["outbound"]["completed_hus"] == 1
    assert horizon["outbound"]["backlog_hus"] == 0
    assert horizon["outbound"]["mean_cycle_s"] == 31
    assert horizon["worker_busy_s"] == 31
    assert horizon["operational_status"] == "partial"
    assert metrics["at_end"]["worker_busy_s"] == 33


def test_queue_does_not_charge_time_before_delayed_arrival() -> None:
    data = fixture((1,), arrival_s=10)
    port = replace(data.profile.ports[0], windows=((ticks(15), ticks(17)),))
    profile = replace(data.profile, ports=(port, *data.profile.ports[1:]))
    outcome = ManualEngine(profile, data.graph, check_invariants=True).run(ticks(20), ticks(30))
    metrics = summary(profile, outcome)
    # Arrival10, reserve14, approach[14,15],service[15,17], stock23, home27.
    assert metrics["at_horizon"]["queues"]["port1"]["job_seconds"] == 4
    assert metrics["at_horizon"]["queues"]["port1"]["mean_jobs"] == pytest.approx(4 / 20)
    assert metrics["at_horizon"]["worker_busy_s"] == 6
    assert metrics["at_horizon"]["inbound"]["mean_cycle_s"] is None
    assert metrics["at_end"]["worker_busy_s"] == 13
    assert metrics["at_end"]["inbound"]["mean_cycle_s"] == 13


def test_empty_run_zero_end_has_no_undefined_numeric_artifacts() -> None:
    data = fixture()
    profile = replace(data.profile, jobs=(), handling_units=())
    outcome = ManualEngine(profile, data.graph, check_invariants=True).run(ticks(20), ticks(30))
    metrics = summary(profile, outcome)
    assert metrics["at_end"]["time_s"] == 0
    assert metrics["at_end"]["worker_busy_s"] == 0
    assert metrics["at_end"]["roster_utilization"] is None
    assert metrics["at_end"]["role_pool_utilization"] == {"receive": None, "ship": None}
    assert metrics["at_end"]["queues"]["port1"]["mean_jobs"] is None
    assert metrics["at_horizon"]["roster_utilization"] == 0
    assert metrics["at_horizon"]["role_pool_utilization"] == {"receive": 0, "ship": None}
