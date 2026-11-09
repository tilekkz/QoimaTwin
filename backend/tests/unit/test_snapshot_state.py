"""State capture between boundaries: blocked actors, pending admissions, scans, receiving.

The engine is advanced with `sched.run(until=...)` and captured at an exact tick. Expected values
are hand-derived from contracts/analytical_fixture.json and contracts/simulation_defaults.json:
handoff ready 32.8 s, feed admission 33 s, shipping arrival 124 s, scan 8 s, receipt 0 arrives at
(0 + 0.5) * 180 = 90 s and takes 90 s of receiver service.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.simulation.snapshot_state import StateCapture
from tests.builders import fixture_order, receipt, run_inputs, scenario


def _engine(bundle: ContractBundle, contracts_dir: Path) -> Engine:
    return Engine(fixture_inputs(bundle, load_fixture(contracts_dir)), check_invariants=True)


def _capture_at(engine: Engine, seconds: Fraction) -> dict[str, Any]:
    tick = engine.ctx.ticks(seconds)
    engine.ctx.sched.run(until=tick + 1)
    return StateCapture(engine)(tick)


def _actor(state: dict[str, Any], actor_id: str) -> dict[str, Any]:
    return next(a for a in state["actors"] if a["actor_id"] == actor_id)


def test_picker_waiting_for_feed_is_blocked_at_home(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = _engine(bundle, contracts_dir)
    state = _capture_at(engine, Fraction(329, 10))
    picker = _actor(state, "P01")
    assert picker["state"] == "BLOCKED"
    assert picker["action"] is None
    home = next(n.pos for n in engine.ctx.inputs.layout.picker_graph.nodes if n.node_id == "I01")
    assert picker["pos"] == [float(v) for v in home]
    induction = next(p.induction_id for p in engine.picking.pickers if p.actor_id == "P01")
    assert state["conveyor"]["admissions"] == [
        {
            "inlet": engine.ctx.topology.induction_inlets[induction],
            "cargo_id": "T001",
            "ready_tick": engine.ctx.ticks(Fraction(164, 5)),
            "owner": "P01",
        }
    ]
    assert state["conveyor"]["cargo"] == [
        {"cargo_id": "T001", "kind": "tote", "order_id": "TEST_001", "target": "PK01"}
    ]


def test_shipper_scan_reserves_pallet_slot(bundle: ContractBundle, contracts_dir: Path) -> None:
    engine = _engine(bundle, contracts_dir)
    state = _capture_at(engine, Fraction(125))
    shipping = state["shipping"]
    assert shipping["buffer"] == []
    assert shipping["scanning"] == [
        {"actor_id": "S01", "order_id": "TEST_001", "until_tick": engine.ctx.ticks(Fraction(132))}
    ]
    pallet = shipping["open_pallet"]
    assert (pallet["parcels"], pallet["reserved"], pallet["expires_tick"]) == ([], 1, None)
    assert _actor(state, "S01")["state"] == "BUSY_SERVICE"
    assert _actor(state, "S02")["state"] == "IDLE"


def test_idle_actor_reports_initial_position(bundle: ContractBundle, contracts_dir: Path) -> None:
    engine = _engine(bundle, contracts_dir)
    state = _capture_at(engine, Fraction(0))
    initial = next(a.initial_pos for a in engine.ctx.inputs.actors.actors if a.actor_id == "R01")
    receiver = _actor(state, "R01")
    assert (receiver["state"], receiver["action"]) == ("IDLE", None)
    assert receiver["pos"] == [float(v) for v in initial]


def test_receipt_in_service_is_captured(bundle: ContractBundle, contracts_dir: Path) -> None:
    scen = scenario([fixture_order()], receipts=[receipt(0)])
    engine = Engine(run_inputs(bundle, contracts_dir, scen), check_invariants=True)
    state = _capture_at(engine, Fraction(90))
    receiving = state["receiving"]
    assert receiving["external"] == []
    assert receiving["area"] == [
        {"pallet_id": "IN_RCP00000", "receipt_id": "RCP00000", "state": "IN_SERVICE"}
    ]
    assert receiving["counts"] == {"accepted": 1, "putaway": 0}
    assert state["ledger"]["accepted"] == [["FIXTURE_01", 500]]
    worker = _actor(state, "R01")
    assert worker["action"]["operation"] == "receive"
    assert worker["action"]["start_tick"] == engine.ctx.ticks(Fraction(90))
    assert worker["action"]["end_tick"] == engine.ctx.ticks(Fraction(180))


def test_two_pallets_on_one_outbound_forklift_is_an_error(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = _engine(bundle, contracts_dir)
    capture = StateCapture(engine)
    capture.events.sealed.update({"PAL_A": ["X"], "PAL_B": ["Y"]})
    with pytest.raises(RuntimeError, match="more than one pallet"):
        capture(0)


def test_pack_snapshot_preserves_order_and_allocated_tote(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = _engine(bundle, contracts_dir)
    state = _capture_at(engine, Fraction(60))
    station = next(s for s in state["stations"] if s["pack_id"] == "PK01")
    assert station["cargo"] == [
        {"cargo_id": "T001", "kind": "tote", "order_id": "TEST_001", "target": "PK01"}
    ]
    assert state["totes"]["allocated"] == ["T001"]


def test_snapshot_terminal_order_status_without_history(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = _engine(bundle, contracts_dir)
    state = _capture_at(engine, Fraction(474))
    assert state["orders"]["status"] == {"TEST_001": "dispatched"}
    assert state["totes"]["allocated"] == []
