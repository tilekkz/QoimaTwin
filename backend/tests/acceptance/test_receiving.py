"""Receiving and putaway gates R1-R3 and I6 (05 §6-7)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.inventory.ledger import LocKind
from app.simulation.engine import RunStatus, Termination
from tests.builders import receipt, run_inputs, scenario, simulate

pytestmark = pytest.mark.acceptance


def _times(engine_events: list[tuple[str, int]], kind: str, grid_tps: int) -> list[Fraction]:
    return [Fraction(t, grid_tps) for k, t in engine_events if k == kind]


def test_R2_processed_receipt_has_service_and_putaway_task(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine, outcome = simulate(run_inputs(bundle, contracts_dir, scenario([], [receipt(0)])))
    tps = engine.ctx.grid.ticks_per_second
    events = [(e.kind, e.at_tick) for e in engine.ctx.recorder.events]
    assert _times(events, "receipt_accepted", tps) == [90]
    assert _times(events, "receipt_processed", tps) == [180]
    # F01: home->pick 6 m / 2 = 3 s, pickup 15 s, pick->drop 22 m / 2 = 11 s, drop 15 s
    assert _times(events, "pallet_putaway", tps) == [224]
    assert outcome.status is RunStatus.COMPLETE
    assert Fraction(outcome.end_tick, tps) == 238  # return 28 m / 2 = 14 s
    assert engine.ctx.ledger.buckets("FIXTURE_01")[LocKind.RESERVE_STAGING] == 500
    assert engine.ctx.ledger.check_conservation() == []


def test_R1_full_reserve_and_area_hold_receipts_outside(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    receipts = [receipt(i) for i in range(3)]
    engine, outcome = simulate(
        run_inputs(
            bundle,
            contracts_dir,
            scenario([], receipts),
            reserve_staging_capacity=1,
            receiving_queue_capacity=1,
        )
    )
    accepted = engine.ctx.recorder.of_kind("receipt_accepted")
    stored = engine.ctx.recorder.of_kind("pallet_putaway")
    assert [e.entity_id for e in accepted] == ["RCP00000", "RCP00001"]
    assert [e.entity_id for e in stored] == ["RCP00000"]
    assert [r.receipt_id for r in engine.receiving.external] == ["RCP00002"]
    assert outcome.status is RunStatus.PARTIAL
    assert outcome.termination is Termination.DEADLOCK


def test_I6_external_receipt_is_not_accepted_inventory(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine, _ = simulate(
        run_inputs(
            bundle,
            contracts_dir,
            scenario([], [receipt(i) for i in range(3)]),
            reserve_staging_capacity=1,
            receiving_queue_capacity=1,
        )
    )
    ledger = engine.ctx.ledger
    # 2000 initial + two accepted receipts of 500; the third stays outside the boundary
    assert ledger.physical_units("FIXTURE_01") == 3000
    assert ledger.check_conservation() == []


def test_R3_putaway_only_changes_ground_reserve(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine, _ = simulate(run_inputs(bundle, contracts_dir, scenario([], [receipt(0)])))
    buckets = engine.ctx.ledger.buckets("FIXTURE_01")
    assert buckets[LocKind.PICKFACE] == 2000
    assert buckets[LocKind.RESERVE_SLOT] == 0
    assert buckets[LocKind.RESERVE_STAGING] == 500
    assert buckets[LocKind.RECEIVING] == 0
    assert buckets[LocKind.INBOUND_VEHICLE] == 0
