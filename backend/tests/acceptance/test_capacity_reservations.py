"""PDF p8: finite queues and engine-level rollback; all times are hand arithmetic."""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.inventory.ledger import LocKind
from app.simulation.engine import Engine
from app.simulation.shipping import Pallet, PalletState
from tests.builders import fixture_order, receipt, run_inputs, scenario, simulate
from tests.flow_builders import flow_engine, parcel, place_at, through

pytestmark = pytest.mark.acceptance


def test_partial_inventory_request_rejects_atomically_and_next_order_runs(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    rejected = fixture_order(order_id="A_SHORT")
    rejected["lines"][1]["quantity"] = 2
    inputs = run_inputs(bundle, contracts_dir, scenario([rejected, fixture_order(1, "B_OK")]))
    lots = tuple(lot.model_copy(update={"quantity": 1}) for lot in inputs.assignment.initial_lots)
    inputs = dataclasses.replace(
        inputs, assignment=inputs.assignment.model_copy(update={"initial_lots": lots})
    )
    engine = Engine(inputs, check_invariants=True)
    through(engine, 0)
    assert [e.entity_id for e in engine.ctx.recorder.of_kind("order_rejected_inventory")] == [
        "A_SHORT"
    ]
    assert not engine.ctx.recorder.of_kind("stock_reserved")
    for holding in engine.ctx.sku_holding.values():
        assert engine.ctx.ledger.on_hand(holding) == 1
        assert engine.ctx.ledger.reserved(holding) == 0
    engine.run()
    assert [e.entity_id for e in engine.ctx.recorder.of_kind("order_dispatched")] == ["B_OK"]
    for sku, holding in engine.ctx.sku_holding.items():
        assert engine.ctx.ledger.reserved(holding) == 0
        assert engine.ctx.ledger.buckets(sku)[LocKind.DISPATCHED] == 1


def test_receiving_two_positions_two_reserve_places_and_five_receipts(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine, _ = simulate(
        run_inputs(
            bundle,
            contracts_dir,
            scenario([], [receipt(i) for i in range(5)]),
            receiving_queue_capacity=2,
            reserve_staging_capacity=2,
        )
    )
    accepted = engine.ctx.recorder.of_kind("receipt_accepted")
    assert [e.entity_id for e in accepted] == [f"RCP{i:05d}" for i in range(4)]
    # First arrivals 90,270; receiving90 + empty6/2 + pickup15 + loaded22/2 + drop15.
    stored = engine.ctx.recorder.of_kind("pallet_putaway")
    assert [engine.ctx.grid.seconds(e.at_tick) for e in stored] == [224, 404]
    assert engine.receiving.staging_used == 2
    assert [p.receipt.receipt_id for p in engine.receiving.area] == ["RCP00002", "RCP00003"]
    assert [r.receipt_id for r in engine.receiving.external] == ["RCP00004"]
    buckets = engine.ctx.ledger.buckets("FIXTURE_01")
    assert buckets[LocKind.RECEIVING] == 2 * 500
    assert buckets[LocKind.RESERVE_STAGING] == 2 * 500
    assert engine.ctx.ledger.physical_units("FIXTURE_01") == 2000 + 4 * 500
    assert engine.ctx.ledger.check_conservation() == []


def _saturated_shipping(engine: Engine) -> Pallet:
    # Eight already sealed physical pallets, each carrying one real ledger parcel.
    for index in range(1, 9):
        pallet = Pallet(engine.ctx.next_id("PAL", 4), PalletState.SEALED)
        pallet.parcels.append(parcel(engine, index))
        engine.shipping.sealed_queue.append(pallet)
        engine.outbound.add_task(pallet)
    ninth = engine.shipping._pallet_with_space()
    assert ninth is not None
    for index in range(9, 19):
        place_at(engine, ninth, parcel(engine, index), 0)
    return ninth


def test_ninth_sealed_pallet_waits_until_forklift_frees_one_of_eight_places(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    ninth = _saturated_shipping(engine)
    through(engine, 17)
    assert len(engine.shipping.sealed_queue) == 8
    assert ninth.state is PalletState.SEAL_PENDING
    assert not engine.ctx.recorder.of_kind("pallet_sealed")
    # Analytical fixture: empty6m / 2m/s + pickup15s frees first place at18.
    through(engine, 18)
    assert len(engine.shipping.sealed_queue) == 8
    assert ninth in engine.shipping.sealed_queue
    seals = engine.ctx.recorder.of_kind("pallet_sealed")
    assert [(e.entity_id, engine.ctx.grid.seconds(e.at_tick)) for e in seals] == [
        ("PAL0009", Fraction(18))
    ]
    engine.run()
    # Each round trip:6/2+15+8/2+15+10/2=42s; ninth dispatch8*42+37=373.
    dispatched = engine.ctx.recorder.of_kind("order_dispatched")
    assert max(engine.ctx.grid.seconds(e.at_tick) for e in dispatched) == 373
    assert len(dispatched) == 8 + 10
    assert engine.ctx.grid.seconds(engine.ctx.now) == 9 * 42


def test_eleventh_parcel_uses_second_pallet_after_first_ten_are_sealed(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    engine.shipping.buffer.extend(parcel(engine, index) for index in range(1, 12))
    engine.ctx.request_dispatch()
    engine.run()
    scans = engine.ctx.recorder.of_kind("parcel_scanned")
    assert [e.payload["pallet_id"] for e in scans] == ["PAL0001"] * 10 + ["PAL0002"]
    # Two shippers scan8s: fifth pair finishes40; last parcel finishes48 and ages300.
    seals = engine.ctx.recorder.of_kind("pallet_sealed")
    assert [engine.ctx.grid.seconds(e.at_tick) for e in seals] == [40, 348]
    assert [len(e.payload["parcel_ids"]) for e in seals] == [10, 1]
    assert engine.metrics.counts()["dispatched_total"] == 11
