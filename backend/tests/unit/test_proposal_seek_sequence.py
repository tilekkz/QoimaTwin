"""Acceptance seek order and pack boundaries use the hand-calculated two-unit fixture."""

import copy
from collections import defaultdict
from typing import Any

from app.exporter.wire_replay import replay_snapshot
from tests.unit.test_proposal_export import proposal as proposal


def _seek(run: dict[str, Any], seconds: float) -> dict[str, Any]:
    tick = round(seconds * run["ticks_per_second"])
    base = max(
        (snapshot for snapshot in run["snapshots"] if snapshot["at_tick"] <= tick),
        key=lambda snapshot: snapshot["at_tick"],
    )
    return replay_snapshot(run, base, tick)


def _assert_stock(snapshot: dict[str, Any], expected: dict[str, int]) -> None:
    by_kind: dict[str, int] = defaultdict(int)
    by_sku: dict[str, int] = defaultdict(int)
    for sku, _lot, kind, _ref, quantity in snapshot["state"]["ledger"]["balances"]:
        by_kind[kind] += quantity
        by_sku[sku] += quantity
    # simulation_defaults gives 2,000 units per SKU; the fixture has no receipts.
    assert dict(by_sku) == {"FIXTURE_01": 2000, "FIXTURE_02": 2000}
    assert dict(by_kind) == expected


def test_seek_sequence_10_80_20_80_is_repeatable_and_does_not_duplicate_stock(
    proposal: dict[str, Any],
) -> None:
    original = copy.deepcopy(proposal)
    seen = [_seek(proposal, seconds) for seconds in (10.0, 80.0, 20.0, 80.0)]
    # First pick finishes at 4/1.2 + 6.15; the second finishes after 20 seconds.
    _assert_stock(seen[0], {"pickface": 3999, "tote": 1})
    _assert_stock(seen[2], {"pickface": 3999, "tote": 1})
    _assert_stock(seen[1], {"pickface": 3998, "parcel": 2})
    _assert_stock(seen[3], {"pickface": 3998, "parcel": 2})
    assert seen[1] == seen[3]
    start = proposal["snapshots"][0]
    for snapshot in seen:
        assert snapshot == replay_snapshot(proposal, start, snapshot["at_tick"])
    assert proposal == original


def test_pack_at_52_and_76_1_moves_two_units_once_when_replayed(
    proposal: dict[str, Any],
) -> None:
    original = copy.deepcopy(proposal)
    started = _seek(proposal, 52.0)
    # 52 + 20 base + 2 lines * 2 + 2 units * 0.05 = 76.1 seconds.
    completed = replay_snapshot(proposal, started, round(76.1 * proposal["ticks_per_second"]))
    _assert_stock(started, {"pickface": 3998, "pack_wip": 2})
    _assert_stock(completed, {"pickface": 3998, "parcel": 2})
    assert replay_snapshot(proposal, started, started["at_tick"]) == started
    assert replay_snapshot(proposal, completed, completed["at_tick"]) == completed
    assert _seek(proposal, 52.0) == started
    assert _seek(proposal, 76.1) == completed
    assert proposal == original
