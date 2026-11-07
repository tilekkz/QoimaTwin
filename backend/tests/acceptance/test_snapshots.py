"""30 s replay snapshots and 60 s chunks on the analytical fixture (05 §10 items 3 and 5, ADR 0010).

Expected times are derived by hand from contracts/analytical_fixture.json: walk 4/8.5/8.5 m at
1.2 m/s, picks 6.15 s each, handoff [29.8, 32.8), pack [52, 76.1), scan done 132, pallet age
timer 132 + 300 = 432, forklift to_pickup [432, 435), pickup [435, 450), to_dock [450, 454),
dispatch 469, home 474. Snapshot boundaries are 0, 30, ..., 450 (the last one <= 474).
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.checkpoint import Snapshot
from app.simulation.chunks import split_events
from app.simulation.engine import Engine, RunOutcome, RunStatus, Termination
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import sha256_hex
from tests.builders import fixture_order, run_inputs, scenario, simulate

pytestmark = pytest.mark.acceptance

STATE_SECTIONS = {
    "actors",
    "conveyor",
    "ledger",
    "orders",
    "receiving",
    "shipping",
    "stations",
    "timers",
    "totes",
}


@pytest.fixture(scope="module")
def run(analytical_run: tuple[Engine, RunOutcome]) -> tuple[Engine, RunOutcome]:
    return analytical_run


def _tick(engine: Engine, seconds: float | Fraction) -> int:
    return engine.ctx.ticks(Fraction(str(seconds)) if isinstance(seconds, float) else seconds)


def _snapshot(engine: Engine, seconds: int) -> Snapshot:
    tick = _tick(engine, seconds)
    return next(s for s in engine.checkpoints.snapshots if s.at_tick == tick)


def _actor(state: dict[str, Any], actor_id: str) -> dict[str, Any]:
    return next(a for a in state["actors"] if a["actor_id"] == actor_id)


def test_boundaries_every_30_s_up_to_end_and_end_unchanged(run: tuple[Engine, RunOutcome]) -> None:
    engine, outcome = run
    assert outcome.status is RunStatus.COMPLETE
    assert outcome.end_tick == _tick(engine, 474)
    expected = [_tick(engine, s) for s in range(0, 451, 30)]
    assert [s.at_tick for s in engine.checkpoints.snapshots] == expected


def test_last_seq_covers_exactly_the_events_at_or_before_boundary(
    run: tuple[Engine, RunOutcome],
) -> None:
    engine, _ = run
    events = engine.ctx.recorder.events
    for snap in engine.checkpoints.snapshots:
        covered = [e.seq for e in events if e.at_tick <= snap.at_tick]
        assert snap.last_seq == (covered[-1] if covered else -1)
        assert covered == list(range(snap.last_seq + 1))


def test_hash_replay_3_snapshot_contains_complete_mutable_state(
    run: tuple[Engine, RunOutcome],
) -> None:
    engine, _ = run
    for snap in engine.checkpoints.snapshots:
        state = snap.state
        assert set(state) == STATE_SECTIONS
        assert {"cells", "cargo", "admissions", "merge_cursors"} <= set(state["conveyor"])
        assert {"balances", "reservations", "claims", "accepted"} <= set(state["ledger"])
        assert snap.state_hash == sha256_hex(state)
        assert "events" not in state
        assert "actions" not in state


def test_snapshot_at_0_includes_phase_3_assignment_at_tick_0(
    run: tuple[Engine, RunOutcome],
) -> None:
    engine, _ = run
    state = _snapshot(engine, 0).state
    assert state["orders"]["queue"] == []
    assert state["orders"]["picking"] == [
        {"order_id": "TEST_001", "actor_id": "P01", "tote_id": "T001"}
    ]
    picker = _actor(state, "P01")
    assert picker["state"] == "TRAVEL"
    assert picker["action"]["start_tick"] == 0
    assert picker["action"]["end_tick"] == _tick(engine, Fraction(10, 3))


def test_snapshot_at_30_picker_in_handoff_with_full_tote(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    state = _snapshot(engine, 30).state
    picker = _actor(state, "P01")
    assert picker["state"] == "BUSY_SERVICE"
    assert picker["action"]["operation"] == "handoff"
    assert picker["action"]["start_tick"] == _tick(engine, 29.8)
    assert picker["action"]["end_tick"] == _tick(engine, 32.8)
    tote = [b for b in state["ledger"]["balances"] if b[2] == "tote"]
    assert sorted((b[0], b[3], b[4]) for b in tote) == [
        ("FIXTURE_01", "T001", 1),
        ("FIXTURE_02", "T001", 1),
    ]
    assert state["ledger"]["claims"] == []
    assert state["ledger"]["reservations"] == []
    assert len(state["totes"]["free"]) == 95
    assert "T001" not in state["totes"]["free"]


def test_snapshot_at_60_tote_in_pack_service(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    state = _snapshot(engine, 60).state
    station = next(s for s in state["stations"] if s["pack_id"] == "PK01")
    assert station["in_service"] == "T001"
    assert station["reserved_wip"] == 1
    packer = _actor(state, "K01")
    assert packer["action"]["operation"] == "pack"
    assert packer["action"]["start_tick"] == _tick(engine, 52)
    assert packer["action"]["end_tick"] == _tick(engine, 76.1)
    assert _actor(state, "P01")["state"] == "IDLE"
    assert state["orders"]["picking"] == []


def test_snapshot_at_90_parcel_on_belt_and_tote_returned(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    state = _snapshot(engine, 90).state
    assert len(state["totes"]["free"]) == 96
    on_belt = [cargo for _cell, cargo in state["conveyor"]["cells"]]
    assert on_belt == ["PCL_TEST_001"]
    assert state["conveyor"]["cargo"] == [
        {"cargo_id": "PCL_TEST_001", "kind": "parcel", "order_id": "TEST_001", "target": "SHIPPING"}
    ]
    station = next(s for s in state["stations"] if s["pack_id"] == "PK01")
    assert station == {
        "pack_id": "PK01",
        "waiting": [],
        "cargo": [],
        "in_service": None,
        "blocked_parcel": None,
        "blocked_since": None,
        "reserved_wip": 0,
    }


def test_snapshot_at_150_open_pallet_and_age_timer(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    state = _snapshot(engine, 150).state
    pallet = state["shipping"]["open_pallet"]
    assert pallet["parcels"] == ["PCL_TEST_001"]
    assert pallet["state"] == "OPEN"
    assert pallet["reserved"] == 0
    assert pallet["first_placement_tick"] == _tick(engine, 132)
    assert pallet["expires_tick"] == _tick(engine, 432)
    assert state["conveyor"]["cells"] == []
    assert _tick(engine, 432) in [t["tick"] for t in state["timers"]]


def test_snapshot_at_450_includes_pickup_completed_at_450(run: tuple[Engine, RunOutcome]) -> None:
    engine, _ = run
    state = _snapshot(engine, 450).state
    shipping = state["shipping"]
    assert shipping["open_pallet"] is None
    assert shipping["sealed_queue"] == []
    carried = shipping["outbound"]["carrying"]
    assert carried["parcels"] == ["PCL_TEST_001"]
    assert carried["state"] == "CLAIMED"
    driver = _actor(state, "F02")
    assert driver["action"]["operation"] == "to_dock"
    assert driver["action"]["start_tick"] == _tick(engine, 450)
    assert driver["action"]["end_tick"] == _tick(engine, 454)
    parcels = [b for b in state["ledger"]["balances"] if b[2] == "parcel"]
    assert sorted(b[0] for b in parcels) == ["FIXTURE_01", "FIXTURE_02"]


def test_hash_replay_5_chunks_and_snapshots_neither_lose_nor_repeat_events(
    run: tuple[Engine, RunOutcome],
) -> None:
    engine, outcome = run
    events = engine.ctx.recorder.events
    chunks = split_events(events, _tick(engine, 60), outcome.end_tick)
    assert len(chunks) == 8  # 474 s lies in [420, 480)
    assert [e.seq for c in chunks for e in c.events] == [e.seq for e in events]
    for snap in engine.checkpoints.snapshots:
        chunk = chunks[snap.at_tick // _tick(engine, 60)]
        after = [e for e in chunk.events if e.seq > snap.last_seq]
        assert all(e.at_tick > snap.at_tick for e in after)


def test_two_runs_give_identical_snapshot_hashes(
    run: tuple[Engine, RunOutcome], bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine, _ = run
    again = Engine(fixture_inputs(bundle, load_fixture(contracts_dir)), check_invariants=True)
    again.run()
    assert [s.state_hash for s in again.checkpoints.snapshots] == [
        s.state_hash for s in engine.checkpoints.snapshots
    ]
    assert len({s.state_hash for s in engine.checkpoints.snapshots}) > 1


def test_late_first_arrival_keeps_initial_state_until_it(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = run_inputs(bundle, contracts_dir, scenario([fixture_order(arrival_s=100)]))
    engine, _ = simulate(inputs)
    early = engine.checkpoints.snapshots[:4]
    assert [s.at_tick for s in early] == [_tick(engine, s) for s in (0, 30, 60, 90)]
    assert {s.last_seq for s in early} == {-1}
    assert len({s.state_hash for s in early}) == 1
    assert all(a["state"] == "IDLE" for a in early[0].state["actors"])
    assert engine.checkpoints.snapshots[4].state_hash != early[0].state_hash


def test_max_drain_caps_snapshots_at_deadline(bundle: ContractBundle, contracts_dir: Path) -> None:
    scen = scenario([fixture_order()], horizon_s=30)
    engine, outcome = simulate(run_inputs(bundle, contracts_dir, scen, max_drain_s=60))
    assert (outcome.status, outcome.termination) == (RunStatus.PARTIAL, Termination.MAX_DRAIN)
    assert outcome.end_tick == _tick(engine, 90)
    assert [s.at_tick for s in engine.checkpoints.snapshots] == [
        _tick(engine, s) for s in (0, 30, 60, 90)
    ]
