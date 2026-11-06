"""Explicit subsystem inputs for the hand-calculated flow acceptance cases."""

from __future__ import annotations

from pathlib import Path

from app.contracts.loader import ContractBundle
from app.inventory.ledger import Location, LocKind
from app.simulation.conveyor_driver import CargoInfo
from app.simulation.engine import Engine
from app.simulation.scheduler import Phase
from app.simulation.shipping import Pallet
from tests.builders import run_inputs, scenario


def flow_engine(bundle: ContractBundle, contracts_dir: Path, pack_s: float = 10) -> Engine:
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([]),
        pack_base_s=pack_s,
        pack_per_line_s=0,
        pack_per_unit_s=0,
    )
    return Engine(inputs, check_invariants=True)


def tote(engine: Engine, index: int, target: str = "PK01") -> CargoInfo:
    cargo = CargoInfo(f"T{index:03d}", "tote", f"FLOW{index:03d}", target)
    engine.picking.free_totes.remove(cargo.cargo_id)
    engine.picking.allocated_totes.add(cargo.cargo_id)
    engine.ctx.ledger.add_initial(
        "FLOW", f"LOT{index:03d}", Location(LocKind.TOTE, cargo.cargo_id), 1
    )
    engine.metrics.order_arrived(cargo.order_id, 0)
    engine.packing.stations[target].reserved_wip += 1
    return cargo


def parcel(engine: Engine, index: int) -> CargoInfo:
    cargo = CargoInfo(f"PCL_FLOW{index:03d}", "parcel", f"FLOW{index:03d}", "SHIPPING")
    engine.ctx.ledger.add_initial(
        "FLOW", f"LOT{index:03d}", Location(LocKind.PARCEL, cargo.cargo_id), 1
    )
    engine.metrics.order_arrived(cargo.order_id, 0)
    engine.metrics.order_packed(cargo.order_id, 0)
    return cargo


def on_belt(engine: Engine, cargo: CargoInfo, cell: str) -> None:
    engine.conveyor.cargo[cargo.cargo_id] = cargo
    engine.conveyor.occupancy[cell] = cargo.cargo_id


def through(engine: Engine, seconds: float) -> None:
    engine.ctx.sched.run(until=engine.ctx.ticks(seconds) + 1)


def full_pack(engine: Engine) -> None:
    station = engine.packing.stations["PK01"]
    engine.packing._start(station, tote(engine, 1))
    station.waiting.extend(tote(engine, i) for i in range(2, 6))
    on_belt(engine, tote(engine, 6), "LOOP_E:11")
    on_belt(engine, tote(engine, 7), "LOOP_E:10")
    engine.ctx.sched.schedule(engine.ctx.ticks(1), Phase.CONVEYOR, engine.conveyor._tick)


def place_at(engine: Engine, pallet: Pallet, cargo: CargoInfo, seconds: float) -> None:
    """Supply a completed scan as input to the pallet state machine."""

    def place() -> None:
        pallet.reserved += 1
        engine.shipping._placed(engine.shipping.shippers[0], pallet, cargo)

    engine.ctx.sched.schedule(engine.ctx.ticks(seconds), Phase.COMPLETION, place)
