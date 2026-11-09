"""D1-D8: hand-calculated pallet races, queue pressure, and dispatch milestones."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from app.simulation.scheduler import Phase
from app.simulation.shipping import Pallet, PalletState
from tests.flow_builders import flow_engine, on_belt, parcel, place_at, through, tote

pytestmark = pytest.mark.acceptance


def _pallet_with_placements(engine: Engine, times: Sequence[float]) -> Pallet:
    pallet = Pallet("PAL_TEST")
    engine.shipping.open_pallet = pallet
    for index, seconds in enumerate(times, 1):
        place_at(engine, pallet, parcel(engine, index), seconds)
    return pallet


def _seal_times(engine: Engine) -> list[float]:
    return [
        float(engine.ctx.grid.seconds(e.at_tick))
        for e in engine.ctx.recorder.of_kind("pallet_sealed")
    ]


def test_D1_two_shippers_cannot_claim_the_same_last_slot(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    pallet = _pallet_with_placements(engine, [0] * 9)
    engine.shipping.buffer.extend(parcel(engine, i) for i in (10, 11))
    through(engine, 0)
    assert len(pallet.parcels) == 9
    assert pallet.reserved == 1
    assert sum(s.busy for s in engine.shipping.shippers) == 1
    assert len(engine.shipping.buffer) == 1
    through(engine, 8)
    assert len(pallet.parcels) == 10
    assert pallet.reserved == 0
    assert _seal_times(engine) == [8]
    assert (
        len(
            [
                a
                for a in engine.ctx.recorder.actions
                if a.operation == "pickup" and a.entity_id == pallet.pallet_id
            ]
        )
        == 1
    )


def test_D2_tenth_placement_seals_at_54_and_stale_timer_cannot_duplicate_task(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    _pallet_with_placements(engine, list(range(0, 60, 6)))
    engine.run()
    assert _seal_times(engine) == [54]
    assert len([a for a in engine.ctx.recorder.actions if a.operation == "pickup"]) == 1
    assert len(engine.ctx.recorder.of_kind("order_dispatched")) == 10


def test_D2_stale_age_timer_does_not_extend_drain_past_forklift_return(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    _pallet_with_placements(engine, list(range(0, 60, 6)))
    outcome = engine.run()
    assert engine.ctx.grid.seconds(outcome.end_tick) == 96  # seal54 + trip37 + return5


def test_D3_partial_pallet_age_seals_at_300_while_upstream_remains_active(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir, pack_s=400)
    pallet = _pallet_with_placements(engine, [0, 6, 12])
    # Real upstream packing remains active on [0,400), with no new parcel before timeout.
    engine.packing.stations["PK02"].waiting.append(tote(engine, 20, "PK02"))
    through(engine, 300)
    assert _seal_times(engine) == [300]
    assert len(pallet.parcels) == 3
    assert engine.ctx.sched.pending_count() > 0


def test_D4_drain_keeps_partial_pallet_timer_and_never_creates_an_empty_pallet(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    _pallet_with_placements(engine, [0, 6, 12])
    outcome = engine.run()
    assert _seal_times(engine) == [300]
    assert engine.ctx.grid.seconds(outcome.end_tick) == 342  # 300 + 37 cargo trip + 5 return
    assert engine.shipping.open_pallet is None
    assert engine.metrics.counts()["dispatched_total"] == 3


def test_D5_full_shipping_buffer_blocks_outbound_cells_until_scan_frees_space(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    engine.ctx.inputs = dataclasses.replace(
        engine.ctx.inputs, config=engine.ctx.config.model_copy(update={"shipping_scan_s": 100})
    )
    pallet = engine.shipping._pallet_with_space()
    assert pallet is not None
    for index, shipper in enumerate(engine.shipping.shippers, 1):
        engine.shipping._scan(shipper, pallet, parcel(engine, index))
    engine.shipping.buffer.extend(parcel(engine, i) for i in range(3, 43))
    engine.ctx.request_dispatch()
    through(engine, 0)  # two in service; exactly 40 remain in the physical buffer
    on_belt(engine, parcel(engine, 43), "OUT_MAIN:45")
    on_belt(engine, parcel(engine, 44), "OUT_MAIN:44")
    engine.ctx.sched.schedule(engine.ctx.ticks(1), Phase.CONVEYOR, engine.conveyor._tick)
    through(engine, 99)
    assert len(engine.shipping.buffer) == 40
    assert engine.conveyor.occupancy == {"OUT_MAIN:45": "PCL_FLOW043", "OUT_MAIN:44": "PCL_FLOW044"}
    through(engine, 100)
    assert len(engine.shipping.buffer) == 38
    assert engine.conveyor.occupancy["OUT_MAIN:45"] == "PCL_FLOW043"
    through(engine, 101)
    assert engine.conveyor.occupancy == {"OUT_MAIN:45": "PCL_FLOW044"}
    assert len(engine.shipping.buffer) == 39


def _dispatch_at_100(bundle: ContractBundle, contracts_dir: Path) -> Engine:
    engine = flow_engine(bundle, contracts_dir)
    engine.ctx.inputs = dataclasses.replace(
        engine.ctx.inputs,
        config=engine.ctx.config.model_copy(update={"shipping_scan_s": 1, "pallet_max_age_s": 5}),
    )
    engine.packing.stations["PK01"].waiting.append(tote(engine, 1))
    engine.ctx.request_dispatch()
    # pack 10, belt 47, scan 1, age 5, forklift 37 => dispatched 100, returned 105.
    return engine


def test_D6_packed_at_10_does_not_count_as_dispatched_before_loading_at_100(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = _dispatch_at_100(bundle, contracts_dir)
    through(engine, 99)
    record = engine.metrics.orders["FLOW001"]
    assert record.packed == engine.ctx.ticks(10)
    assert record.dispatched is None
    assert engine.metrics.counts()["dispatched_total"] == 0
    through(engine, 100)
    assert engine.metrics.orders["FLOW001"].dispatched == engine.ctx.ticks(100)
    assert engine.metrics.counts()["dispatched_total"] == 1


def test_D7_dispatch_is_once_at_dock_and_return_does_not_start_another_shipment(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = _dispatch_at_100(bundle, contracts_dir)
    through(engine, 100)
    assert (engine.outbound.busy,) == (True,)
    assert len(engine.ctx.recorder.of_kind("order_dispatched")) == 1
    outcome = engine.run()
    assert engine.ctx.grid.seconds(outcome.end_tick) == 105
    assert not engine.outbound.busy
    assert len(engine.ctx.recorder.of_kind("order_dispatched")) == 1


def test_D8_timeout_waits_for_scan_reservation_and_seals_once_at_304(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    pallet = _pallet_with_placements(engine, [0])
    second = parcel(engine, 2)
    engine.ctx.sched.schedule(
        engine.ctx.ticks(296), Phase.CONVEYOR, lambda: engine.shipping.accept(second)
    )
    through(engine, 300)
    assert pallet.state is PalletState.SEAL_PENDING
    assert pallet.reserved == 1
    assert len(pallet.parcels) == 1
    assert engine.shipping._pallet_with_space() is None
    assert _seal_times(engine) == []
    through(engine, 304)
    assert pallet.reserved == 0
    assert len(pallet.parcels) == 2
    assert _seal_times(engine) == [304]
    assert len([a for a in engine.ctx.recorder.actions if a.operation == "pickup"]) == 1
    engine.run()
    assert _seal_times(engine) == [304]
    assert len(engine.ctx.recorder.of_kind("order_dispatched")) == 2
