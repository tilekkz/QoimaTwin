"""K1-K4: seven known jobs, finite waiting, and a timed output closure."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from app.simulation.recorder import ActorState
from tests.flow_builders import flow_engine, full_pack, on_belt, parcel, through, tote

pytestmark = pytest.mark.acceptance


def test_K1_six_parallel_packers_and_seventh_waits_ten_seconds(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    for index, pack_id in enumerate(["PK01", "PK01", "PK02", "PK03", "PK04", "PK05", "PK06"], 1):
        engine.packing.stations[pack_id].waiting.append(tote(engine, index, pack_id))
    engine.ctx.request_dispatch()
    through(engine, 0)
    assert sum(len(s.waiting) for s in engine.packing.stations.values()) == 1
    through(engine, 20)
    actions = [a for a in engine.ctx.recorder.actions if a.operation == "pack"]
    intervals = sorted(
        (engine.ctx.grid.seconds(a.start_tick), engine.ctx.grid.seconds(a.end_tick))
        for a in actions
    )
    assert intervals == [(Fraction(0), Fraction(10))] * 6 + [(Fraction(10), Fraction(20))]
    assert sum(start for start, _ in intervals) == 10  # all seven were ready at zero


def test_K2_waiting_capacity_excludes_service_and_sixth_stays_outside(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    full_pack(engine)
    through(engine, 1)
    station = engine.packing.stations["PK01"]
    assert station.in_service is not None
    assert station.in_service.cargo_id == "T001"
    assert [cargo.cargo_id for cargo in station.waiting] == ["T002", "T003", "T004", "T005"]
    assert "T006" in engine.conveyor.occupancy.values()
    assert not engine.packing.can_accept("PK01")


def _blocked_output(
    bundle: ContractBundle,
    contracts_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Engine:
    engine = flow_engine(bundle, contracts_dir)
    station = engine.packing.stations["PK01"]
    station.waiting.extend(tote(engine, index) for index in (1, 2))
    obstacle = parcel(engine, 90)
    on_belt(engine, obstacle, station.outlet)
    original_route = engine.conveyor._route

    def route(cargo_id: str, cell: str) -> str:
        if cargo_id == obstacle.cargo_id and engine.ctx.now < engine.ctx.ticks(15):
            return cell  # explicit test outage: physical parcel holds this output cell
        return original_route(cargo_id, cell)

    monkeypatch.setattr(engine.conveyor, "_route", route)
    engine.ctx.request_dispatch()
    return engine


def test_K3_blocked_output_prevents_next_pack_until_acceptance(
    bundle: ContractBundle,
    contracts_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _blocked_output(bundle, contracts_dir, monkeypatch)
    through(engine, 14)
    packed = engine.ctx.recorder.of_kind("order_packed")
    assert [engine.ctx.grid.seconds(e.at_tick) for e in packed] == [10]
    assert len(engine.ctx.recorder.of_kind("pack_started")) == 1
    through(engine, 15)
    blocked = [a for a in engine.ctx.recorder.actions if a.state is ActorState.BLOCKED]
    assert [
        (engine.ctx.grid.seconds(a.start_tick), engine.ctx.grid.seconds(a.end_tick))
        for a in blocked
    ] == [(Fraction(10), Fraction(15))]
    assert [
        engine.ctx.grid.seconds(e.at_tick) for e in engine.ctx.recorder.of_kind("pack_started")
    ] == [0, 15]


def test_K4_tote_returns_before_blocked_parcel_releases_station_reservation(
    bundle: ContractBundle,
    contracts_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _blocked_output(bundle, contracts_dir, monkeypatch)
    station = engine.packing.stations["PK01"]
    through(engine, 10)
    assert engine.picking.free_totes.count("T001") == 1
    assert (station.blocked_parcel, station.reserved_wip) == ("PCL_FLOW001", 2)
    through(engine, 15)
    assert station.blocked_parcel is None
    assert station.reserved_wip == 1
    assert engine.picking.free_totes.count("T001") == 1
