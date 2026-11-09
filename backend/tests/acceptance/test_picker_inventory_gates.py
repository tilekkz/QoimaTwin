"""Gates S3, S4, S5 and I7 (05 §2, §6) on the full layout, with check_invariants=True.

Every expected number is spec arithmetic or a fact of the layout, never engine output:
- S3: pick = pick_base_s + pick_per_unit_s * 100 = 6 + 0.15 * 100 = 21 s (01 §7);
  I01 -> N_A01_Z16 is 4 m (G2), so one walk is 4 / 1.2 = 10/3 s.
- S4: free pickers are taken by stable actor ID (01 §6, ADR 0009).
- S5: in the analytical fixture P01 waits BLOCKED_INDUCTION on [32.8, 33.0) s
  (contracts/analytical_fixture.json: ready 32.8 s, first admission on the next whole second).
- I7: no replenishment (01 §7): accepted receipts stay in reserve; active pick face stays empty.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.inventory.ledger import LocKind
from app.simulation.engine import Engine
from app.simulation.recorder import Action, ActorState
from app.simulation.run_status import RunStatus, Termination
from tests.builders import receipt, run_inputs, scenario, simulate
from tests.flow_builders import full_pack, on_belt, tote

pytestmark = pytest.mark.acceptance


def _order(order_id: str, arrival_s: float, sku: str, quantity: int) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "arrival_s": arrival_s,
        "lines": [{"sku_id": sku, "quantity": quantity}],
    }


def _run(
    bundle: ContractBundle,
    contracts_dir: Path,
    orders: list[dict[str, Any]],
    receipts: list[dict[str, Any]] | None = None,
    horizon_s: float = 1200,
) -> Engine:
    engine, _ = simulate(run_inputs(bundle, contracts_dir, scenario(orders, receipts, horizon_s)))
    return engine


def _assignments(engine: Engine) -> dict[str, dict[str, Any]]:
    events = engine.ctx.recorder.of_kind("order_assigned")
    return {e.entity_id: {**e.payload, "at_tick": e.at_tick} for e in events}


def _actions(engine: Engine, actor_id: str) -> list[Action]:
    return [a for a in engine.ctx.recorder.actions if a.actor_id == actor_id]


def test_S3_one_sku_quantity_100_is_one_stop_and_a_21_second_pick(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    config = bundle.config
    assert (config.pick_base_s, config.pick_per_unit_s, config.walk_speed_mps) == (6, 0.15, 1.2)
    engine = _run(bundle, contracts_dir, [_order("S3", 0, "FIXTURE_01", 100)])
    ticks = engine.ctx.grid.ticks
    picker = _assignments(engine)["S3"]["actor_id"]
    actions = _actions(engine, picker)
    picks = [a for a in actions if a.operation == "pick"]
    assert len(picks) == 1
    assert picks[0].end_tick - picks[0].start_tick == ticks(Fraction(21))
    trips = [a for a in actions if a.state is ActorState.TRAVEL]
    assert len(trips) == 2  # one walk to the bay and one back home
    assert all(a.end_tick - a.start_tick == ticks(Fraction(10, 3)) for a in trips)
    assert engine.last_outcome is not None
    assert engine.last_outcome.status is RunStatus.COMPLETE


def test_S4_two_free_pickers_of_one_home_take_orders_by_stable_actor_id(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    homes = {a.actor_id: a.home_node_id for a in bundle.actors.actors}
    assert homes["P01"] == homes["P02"] == "I01"
    orders = [_order("A1", 0, "FIXTURE_01", 1), _order("A2", 0, "FIXTURE_02", 1)]
    engine = _run(bundle, contracts_dir, orders)
    assigned = _assignments(engine)
    assert (assigned["A1"]["actor_id"], assigned["A2"]["actor_id"]) == ("P01", "P02")
    assert assigned["A1"]["tote_id"] != assigned["A2"]["tote_id"]
    assert assigned["A1"]["at_tick"] == assigned["A2"]["at_tick"] == 0
    for actor in ("P01", "P02"):
        spans = sorted((a.start_tick, a.end_tick) for a in _actions(engine, actor))
        assert all(prev[1] <= nxt[0] for prev, nxt in pairwise(spans))


def test_S5_picker_holding_a_blocked_tote_gets_no_next_order(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    # TEST_001 is the analytical fixture order; NEXT arrives while P01 is blocked at 32.9 s.
    orders = [_order("TEST_001", 0, "FIXTURE_01", 1), _order("NEXT", 32.9, "FIXTURE_02", 1)]
    orders[0]["lines"].append({"sku_id": "FIXTURE_02", "quantity": 1})
    engine = _run(bundle, contracts_dir, orders)
    ticks = engine.ctx.grid.ticks
    blocked = [a for a in _actions(engine, "P01") if a.state is ActorState.BLOCKED]
    assert [(a.start_tick, a.end_tick) for a in blocked] == [
        (ticks(Fraction(164, 5)), ticks(Fraction(33)))
    ]
    nxt = _assignments(engine)["NEXT"]
    assert nxt["at_tick"] == ticks(Fraction(329, 10))
    assert nxt["actor_id"] == "P02"  # P01 would win by actor ID if it were free
    assert nxt["tote_id"] != _assignments(engine)["TEST_001"]["tote_id"]


def test_I7_reserve_stock_never_fills_an_empty_active_pick_face(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    units = bundle.config.ground_units_per_sku
    orders = [_order("DRAIN", 0, "FIXTURE_02", units), _order("LATE", 900, "FIXTURE_02", 1)]
    engine = _run(bundle, contracts_dir, orders, [receipt(0, "FIXTURE_02", 500)])
    buckets = engine.ctx.ledger.buckets("FIXTURE_02")
    assert buckets[LocKind.PICKFACE] == 0
    assert buckets[LocKind.RESERVE_STAGING] + buckets[LocKind.RESERVE_SLOT] == 500
    assert buckets[LocKind.DISPATCHED] == units
    assigned = _assignments(engine)
    assert "DRAIN" in assigned and "LATE" not in assigned
    counts = engine.metrics.counts()
    assert (counts["dispatched_total"], counts["unfulfilled_inventory_total"]) == (1, 1)
    outcome = engine.last_outcome
    assert outcome is not None
    assert (outcome.status, outcome.termination) == (
        RunStatus.PARTIAL,
        Termination.UNFULFILLED_INVENTORY,
    )


def _fill_feed_to_blocked_divert(engine: Engine) -> str:
    full_pack(engine)
    inlet = engine.ctx.topology.induction_inlets["I01"]
    cell = inlet
    for index in range(8, 96):
        if cell in engine.conveyor.occupancy:
            return inlet
        on_belt(engine, tote(engine, index), cell)
        next_cell = engine.ctx.topology.next_cell_towards(cell, "PK01")
        assert next_cell is not None
        cell = next_cell
    raise AssertionError("fixture route did not reach the occupied divert")


def test_S5_full_feed_preserves_picker_and_tote_ownership(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    # Seed blocked service at t0, then shift the analytical order by1s to preserve phase order.
    orders = [_order("FIRST", 1, "FIXTURE_01", 1), _order("NEXT", 33.9, "FIXTURE_02", 1)]
    orders[0]["lines"].append({"sku_id": "FIXTURE_02", "quantity": 1})
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario(orders, horizon_s=35),
        pack_base_s=1000,
        pack_per_line_s=0,
        pack_per_unit_s=0,
        max_drain_s=0,
    )
    engine = Engine(inputs, check_invariants=True)
    inlet = _fill_feed_to_blocked_divert(engine)
    occupant = engine.conveyor.occupancy[inlet]
    engine.run()
    assert engine.conveyor.occupancy[inlet] == occupant
    first = engine.picking.jobs["FIRST"]
    assert first.picker.actor_id == "P01" and first.picker.busy
    assert first.tote_id in engine.picking.allocated_totes
    assert first.tote_id not in engine.picking.free_totes
    assert any(request.cargo_id == first.tote_id for request in engine.conveyor.requests)
    assert _assignments(engine)["NEXT"]["actor_id"] == "P02"
    assert not any(e.entity_id == "FIRST" for e in engine.ctx.recorder.of_kind("tote_inducted"))
