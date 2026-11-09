"""Exact integer time (ADR 0002)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.simulation.clock import TimeGrid, TimeGridError


@pytest.fixture(scope="module")
def grid(layout: Layout, config: SimulationConfig) -> TimeGrid:
    return TimeGrid.for_inputs(layout, config)


def test_default_inputs_need_three_million_ticks_per_second(grid: TimeGrid) -> None:
    assert grid.ticks_per_second == 3_000_000


def test_walk_of_four_metres_is_exact(grid: TimeGrid) -> None:
    ticks = grid.ticks(Fraction(4) / Fraction(6, 5))
    assert ticks == 10_000_000
    assert grid.seconds(ticks) == Fraction(10, 3)


def test_fixture_handoff_is_exactly_32_8_seconds(grid: TimeGrid) -> None:
    walk = grid.ticks(Fraction(21) / Fraction(6, 5))
    pick = 2 * grid.ticks(Fraction(6) + Fraction(15, 100))
    handoff = grid.ticks(Fraction(3))
    assert walk + pick + handoff == grid.ticks(Fraction(164, 5))


def test_ceil_to_second_moves_fraction_up_and_keeps_integer(grid: TimeGrid) -> None:
    tps = grid.ticks_per_second
    assert grid.ceil_to_second(grid.ticks(Fraction(164, 5))) == 33 * tps
    assert grid.ceil_to_second(33 * tps) == 33 * tps
    assert grid.ceil_to_second(33 * tps + 1) == 34 * tps
    assert grid.ceil_to_second(0) == 0


def test_boundary_times_around_33_seconds(grid: TimeGrid) -> None:
    tps = grid.ticks_per_second
    assert grid.ceil_to_second(grid.ticks(Fraction(32999, 1000))) == 33 * tps
    assert grid.ceil_to_second(grid.ticks(Fraction(33001, 1000))) == 34 * tps


def test_unrepresentable_duration_is_rejected(grid: TimeGrid) -> None:
    with pytest.raises(TimeGridError):
        grid.ticks(Fraction(1, 7))


def test_negative_duration_is_rejected(grid: TimeGrid) -> None:
    with pytest.raises(TimeGridError):
        grid.ticks(Fraction(-1))


def test_float_seconds_for_export(grid: TimeGrid) -> None:
    assert grid.to_seconds_float(grid.ticks(Fraction(761, 10))) == 76.1


def test_grid_from_explicit_durations() -> None:
    grid = TimeGrid.from_durations([Fraction(1, 3), Fraction(1, 8)])
    assert grid.ticks_per_second == 3_000_000
    assert TimeGrid.from_durations([]).ticks_per_second == 1_000_000


def test_grid_rejects_excessive_resolution() -> None:
    with pytest.raises(TimeGridError):
        TimeGrid.from_durations([Fraction(1, 999_999_937)])
