"""Isolated end-to-end fixture: one order from arrival to dispatch (05 §3, S1, S2).

Expected numbers come from contracts/analytical_fixture.json, never from the engine.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest

from app.simulation.engine import Engine, RunOutcome, RunStatus, Termination
from app.simulation.recorder import ActorState

pytestmark = pytest.mark.acceptance


@pytest.fixture(scope="module")
def fixture(analytical_fixture: dict[str, Any]) -> dict[str, Any]:
    return analytical_fixture


@pytest.fixture(scope="module")
def run(analytical_run: tuple[Engine, RunOutcome]) -> tuple[Engine, RunOutcome]:
    return analytical_run


def _seconds(engine: Engine, kind: str) -> list[Fraction]:
    grid = engine.ctx.grid
    return [grid.seconds(e.at_tick) for e in engine.ctx.recorder.of_kind(kind)]


def _expected(fixture: dict[str, Any], name: str) -> Fraction:
    return Fraction(str(fixture["expected"][name]))


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("handoff_ready", "handoff_ready_s"),
        ("tote_inducted", "feed_accepted_s"),
        ("pack_started", "pack_started_s"),
        ("order_packed", "pack_completed_s"),
        ("parcel_outfed", "outfeed_accepted_s"),
        ("shipping_arrived", "shipping_buffer_arrival_s"),
        ("parcel_scanned", "scan_completed_s"),
        ("pallet_sealed", "pallet_sealed_s"),
        ("order_dispatched", "dispatched_s"),
    ],
)
def test_milestone_times(
    run: tuple[Engine, RunOutcome], fixture: dict[str, Any], kind: str, name: str
) -> None:
    engine, _ = run
    assert _seconds(engine, kind) == [_expected(fixture, name)]


def test_S1_route_walk_and_pick_service(
    run: tuple[Engine, RunOutcome], fixture: dict[str, Any]
) -> None:
    engine, _ = run
    grid = engine.ctx.grid
    assert engine.metrics.distance_m["P01"] == _expected(fixture, "picker_distance_m")
    picker = [a for a in engine.ctx.recorder.actions if a.actor_id == "P01"]
    walk = sum(
        grid.seconds(a.end_tick - a.start_tick) for a in picker if a.state is ActorState.TRAVEL
    )
    pick = sum(grid.seconds(a.end_tick - a.start_tick) for a in picker if a.operation == "pick")
    assert walk == _expected(fixture, "walk_s")
    assert pick == _expected(fixture, "pick_service_s")


def test_S2_blocked_induction_is_0_2_seconds(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    grid = engine.ctx.grid
    blocked = [a for a in engine.ctx.recorder.actions if a.state is ActorState.BLOCKED]
    picker_block = [a for a in blocked if a.actor_id == "P01"]
    assert len(picker_block) == 1
    assert grid.seconds(picker_block[0].start_tick) == Fraction(164, 5)
    assert grid.seconds(picker_block[0].end_tick) == 33


def test_first_conveyor_move_and_transport_lengths(
    run: tuple[Engine, RunOutcome], fixture: dict[str, Any]
) -> None:
    engine, _ = run
    grid = engine.ctx.grid
    tote_moves = [t for t in engine.conveyor.transfers if t.cargo_id == "T001"]
    assert tote_moves[0].source == "inlet"
    assert grid.seconds(tote_moves[1].at_tick) == _expected(fixture, "first_conveyor_move_s")
    belt_cells = [t for t in tote_moves if t.source != "inlet"]
    assert len(belt_cells) == _expected(fixture, "to_pack_conveyor_m")
    parcel_cells = [t for t in engine.conveyor.transfers if t.cargo_id.startswith("PCL_")]
    assert len([t for t in parcel_cells if t.source != "inlet"]) == _expected(
        fixture, "to_shipping_conveyor_m"
    )


def test_forklift_trip(run: tuple[Engine, RunOutcome], fixture: dict[str, Any]) -> None:
    engine, _ = run
    grid = engine.ctx.grid
    trip = [a for a in engine.ctx.recorder.actions if a.actor_id == "F02"]
    ops = [(a.operation, grid.seconds(a.start_tick), grid.seconds(a.end_tick)) for a in trip]
    sealed = _expected(fixture, "pallet_sealed_s")
    assert ops == [
        ("to_pickup", sealed, sealed + 3),
        ("pickup", sealed + 3, sealed + 18),
        ("to_dock", sealed + 18, sealed + 22),
        ("loading", sealed + 22, _expected(fixture, "dispatched_s")),
        ("to_home", _expected(fixture, "dispatched_s"), _expected(fixture, "forklift_available_s")),
    ]


def test_run_drains_completely_and_conserves_stock(run: tuple[Engine, RunOutcome]) -> None:
    engine, outcome = run
    assert outcome.status is RunStatus.COMPLETE
    assert outcome.termination is Termination.DRAINED
    assert engine.ctx.grid.seconds(outcome.end_tick) == 474
    assert engine.ctx.ledger.check_conservation() == []
    assert len(engine.picking.free_totes) == 96
    assert engine.metrics.counts() == {
        "arrived_total": 1,
        "packed_total": 1,
        "dispatched_total": 1,
        "unfulfilled_inventory_total": 0,
    }


def test_events_are_ordered_by_time_phase_seq(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    keys = [(e.at_tick, int(e.phase), e.seq) for e in engine.ctx.recorder.events]
    assert keys == sorted(keys)
    assert [e.seq for e in engine.ctx.recorder.events] == list(range(len(keys)))
