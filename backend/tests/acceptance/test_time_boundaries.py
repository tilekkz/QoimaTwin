"""Exact admission boundary: no epsilon may move an admission to an earlier tick (ADR 0002)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from tests.builders import fixture_order, run_inputs, scenario, simulate

pytestmark = pytest.mark.acceptance


@pytest.mark.parametrize(
    ("arrival", "feed", "dispatch", "home"),
    [
        (0.2, 33, Fraction(469), Fraction(474)),
        (0.200001, 34, Fraction(470), Fraction(475)),
    ],
)
def test_arrival_shift_moves_feed_tick_exactly(
    bundle: ContractBundle,
    contracts_dir: Path,
    arrival: float,
    feed: int,
    dispatch: Fraction,
    home: Fraction,
) -> None:
    engine, outcome = simulate(
        run_inputs(bundle, contracts_dir, scenario([fixture_order(arrival)]))
    )
    grid = engine.ctx.grid
    ready = engine.ctx.recorder.of_kind("handoff_ready")[0]
    inducted = engine.ctx.recorder.of_kind("tote_inducted")[0]
    assert grid.seconds(ready.at_tick) == Fraction(164, 5) + Fraction(str(arrival))
    assert grid.seconds(inducted.at_tick) == feed
    dispatched = engine.ctx.recorder.of_kind("order_dispatched")[0]
    assert grid.seconds(dispatched.at_tick) == dispatch
    assert grid.seconds(outcome.end_tick) == home
