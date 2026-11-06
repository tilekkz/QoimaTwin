"""Settled-state checks with deliberate corruption, independent of engine output."""

from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.contracts.scenario import Receipt
from app.simulation.conveyor_driver import CargoInfo
from app.simulation.engine import Engine
from app.simulation.invariants import InvariantViolation, check_invariants
from app.simulation.receiving import InboundPallet
from app.simulation.scheduler import Phase
from app.simulation.shipping import Pallet
from tests.builders import run_inputs, scenario


@pytest.fixture
def engine(bundle: ContractBundle, contracts_dir: Path) -> Engine:
    return Engine(run_inputs(bundle, contracts_dir, scenario([])), check_invariants=True)


def test_valid_initial_state(engine: Engine) -> None:
    check_invariants(engine)


@pytest.mark.parametrize("mutation", ["lost", "duplicate", "overlap", "unknown"])
def test_tote_pool_corruption(engine: Engine, mutation: str) -> None:
    pool = engine.picking.free_totes
    if mutation == "lost":
        pool.pop()
    elif mutation == "duplicate":
        pool.append("T001")
    elif mutation == "overlap":
        engine.picking.allocated_totes.add("T001")
    else:
        pool[-1] = "T097"
    with pytest.raises(InvariantViolation, match="tote"):
        check_invariants(engine)


def test_conservation_corruption(engine: Engine) -> None:
    holding = next(iter(engine.ctx.sku_holding.values()))
    engine.ctx.ledger._balances[holding] += 1
    with pytest.raises(InvariantViolation, match="units"):
        check_invariants(engine)


def test_cargo_cannot_occupy_two_cells(engine: Engine) -> None:
    cells = list(engine.ctx.topology.successors)[:2]
    engine.conveyor.occupancy = dict.fromkeys(cells, "T001")
    with pytest.raises(InvariantViolation, match="cell"):
        check_invariants(engine)


@pytest.mark.parametrize("location", ["pack", "shipping", "sealed", "receiving", "reserve"])
def test_capacity_limits(engine: Engine, location: str) -> None:
    cargo = CargoInfo("T001", "tote", "O1", "PK01")
    if location == "pack":
        engine.packing.stations["PK01"].waiting.extend([cargo] * 5)
    elif location == "shipping":
        engine.shipping.buffer.extend([cargo] * 41)
    elif location == "sealed":
        engine.shipping.sealed_queue.extend(Pallet(f"P{i}") for i in range(9))
    elif location == "receiving":
        receipt = Receipt(receipt_id="R", arrival_s=0, sku_id="X", quantity=1)
        engine.receiving.area.extend(InboundPallet(receipt, f"P{i}") for i in range(9))
    else:
        engine.receiving.staging_used = 41
    with pytest.raises(InvariantViolation, match="capacity"):
        check_invariants(engine)


@pytest.mark.parametrize("placed,reserved", [(10, 1), (0, -1)])
def test_pallet_slots(engine: Engine, placed: int, reserved: int) -> None:
    parcel = CargoInfo("P1", "parcel", "O1", "SHIPPING")
    engine.shipping.open_pallet = Pallet("P", parcels=[parcel] * placed, reserved=reserved)
    with pytest.raises(InvariantViolation, match="pallet"):
        check_invariants(engine)


def test_negative_reserved_wip(engine: Engine) -> None:
    engine.packing.stations["PK01"].reserved_wip = -1
    with pytest.raises(InvariantViolation, match="reserved_wip"):
        check_invariants(engine)


def test_hook_checks_after_all_phases(engine: Engine) -> None:
    pool = engine.picking.free_totes
    engine.ctx.sched.schedule(0, Phase.COMPLETION, lambda: pool.remove("T096"))
    engine.ctx.sched.schedule(0, Phase.ARRIVAL, lambda: pool.append("T096"))
    engine.run()


def test_hook_fails_at_settled_tick(engine: Engine) -> None:
    engine.ctx.sched.schedule(7, Phase.COMPLETION, lambda: engine.picking.free_totes.remove("T096"))
    with pytest.raises(InvariantViolation, match="tick=7"):
        engine.run()
