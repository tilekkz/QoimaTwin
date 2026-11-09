"""Manual timelines, repeated backward seeks and cut-off motion use observed state."""

from copy import deepcopy

from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run
from app.v3.run_replay import replay_manual
from app.v3.run_values import record
from tests.v3.test_run_fixtures import manual_profile


def test_inbound_repeated_forward_backward_seek_never_duplicates_units() -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(80_000_000, 100_000_000)
    run = build_manual_run(
        profile,
        graph,
        outcome,
        graph_document=document,
        end_tick_limit=100_000_000,
        snapshot_interval_ticks=10_000_000,
    )
    before = deepcopy(run)
    states = [replay_manual(run, seconds * 1_000_000) for seconds in (10, 80, 20, 80)]
    assert states[0]["wip_units"] == states[2]["wip_units"] == [["SKU1", 24]]
    assert states[0]["stock_units"] == states[2]["stock_units"] == []
    assert states[1] == states[3] == record(outcome.at_horizon)
    assert states[1]["stock_units"] == [["SKU1", 24]]
    assert states[1]["wip_units"] == states[1]["outside_units"] == []
    assert replay_manual(run, 22_999_999)["wip_units"] == [["SKU1", 24]]
    assert replay_manual(run, 23_000_000)["stock_units"] == [["SKU1", 24]]
    assert outcome.at_end.tick == 33_000_000
    assert replay_manual(run, 33_000_000) == record(outcome.at_end)
    assert run == before


def test_outbound_shipping_boundary_precedes_paid_return_completion() -> None:
    profile, graph, document = manual_profile("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(32_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    assert replay_manual(run, 30_999_999)["shipped_units"] == []
    at_ship = replay_manual(run, 31_000_000)
    assert at_ship["shipped_units"] == [["SKU1", 24]]
    assert at_ship["wip_units"] == at_ship["stock_units"] == []
    assert at_ship["status"] == "partial"
    assert at_ship["jobs"][0]["state"] == "returning"
    assert replay_manual(run, 32_000_000) == record(outcome.at_horizon)
    assert replay_manual(run, 33_000_000) == record(outcome.at_end)


def test_cutoff_keeps_planned_motion_without_future_completion_event() -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(15_000_000, 18_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=18_000_000
    )
    state = replay_manual(run, 18_000_000)
    worker = next(row for row in state["workers"] if row["actor_id"] == "R01")
    assert worker["node_id"] is None
    assert worker["motion"]["start_tick"] == 17_000_000
    assert worker["motion"]["end_tick"] == 22_000_000
    assert state["wip_units"] == [["SKU1", 24]]
    assert state["stock_units"] == []
    assert max(event["tick"] for event in run["events"]) <= 18_000_000
    assert state == record(outcome.at_end)
