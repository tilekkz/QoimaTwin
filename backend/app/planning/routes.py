"""Exact relocation route of one swap (01 §9): both orientations on the picker graph.

Orientation "a_first": home, A, buffer, B, A, buffer, B, home (A->buffer, B->A, buffer->B).
Orientation "b_first" exchanges A and B. Labor = route metres / walk speed + 6 take/place.
On an undirected graph both totals are equal; ties keep "a_first".
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Literal

from app.contracts.base import exact
from app.contracts.config import SimulationConfig
from app.planning.geometry import PlanningGeometry

HANDLINGS_PER_SWAP = 6


@dataclass(frozen=True, slots=True)
class WorkerRates:
    """Relocation worker walking speed and the fixed take/place duration (exact)."""

    walk_speed_mps: Fraction
    take_or_place_s: Fraction

    @classmethod
    def of(cls, config: SimulationConfig) -> WorkerRates:
        return cls(exact(config.walk_speed_mps), exact(config.relocation_take_or_place_s))


@dataclass(frozen=True, slots=True)
class SwapRoute:
    orientation: Literal["a_first", "b_first"]
    first_slot: str
    second_slot: str
    stops: tuple[str, ...]
    distance_m: Fraction


@dataclass(frozen=True, slots=True)
class SwapEvaluation:
    slot_a: str
    slot_b: str
    a_first: SwapRoute
    b_first: SwapRoute
    chosen: SwapRoute
    walk_s: Fraction
    handling_s: Fraction

    @property
    def labor_s(self) -> Fraction:
        return self.walk_s + self.handling_s

    @property
    def alternate(self) -> SwapRoute:
        return self.b_first if self.chosen is self.a_first else self.a_first


def _route(
    geo: PlanningGeometry,
    orientation: Literal["a_first", "b_first"],
    first: str,
    second: str,
) -> SwapRoute:
    a, b = geo.service_node[first], geo.service_node[second]
    home, buffer = geo.home_node, geo.buffer_node
    stops = (home, a, buffer, b, a, buffer, b, home)
    distance = sum((geo.distance(x, y) for x, y in pairwise(stops)), Fraction(0))
    return SwapRoute(orientation, first, second, stops, distance)


def orient(
    geo: PlanningGeometry, slot_a: str, slot_b: str
) -> tuple[SwapRoute, SwapRoute, SwapRoute]:
    """Both orientations and the chosen (shorter; "a_first" on a tie) route."""
    geo.slot_cost(slot_a)
    geo.slot_cost(slot_b)
    a_first = _route(geo, "a_first", slot_a, slot_b)
    b_first = _route(geo, "b_first", slot_b, slot_a)
    return a_first, b_first, (a_first if a_first.distance_m <= b_first.distance_m else b_first)


def evaluate_swap(
    geo: PlanningGeometry, config: SimulationConfig, slot_a: str, slot_b: str
) -> SwapEvaluation:
    """Both orientations of swapping the lots on two ground slots; the shorter is chosen."""
    return evaluate_swap_at(geo, WorkerRates.of(config), slot_a, slot_b)


def evaluate_swap_at(
    geo: PlanningGeometry, rates: WorkerRates, slot_a: str, slot_b: str
) -> SwapEvaluation:
    a_first, b_first, chosen = orient(geo, slot_a, slot_b)
    return SwapEvaluation(
        slot_a=slot_a,
        slot_b=slot_b,
        a_first=a_first,
        b_first=b_first,
        chosen=chosen,
        walk_s=chosen.distance_m / rates.walk_speed_mps,
        handling_s=HANDLINGS_PER_SWAP * rates.take_or_place_s,
    )
