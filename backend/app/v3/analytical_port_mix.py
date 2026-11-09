"""F1: common declared port mix and distances, evaluated without a warehouse engine."""

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from app.v3.analytical_common import require_count, require_rational, require_tuple


@dataclass(frozen=True, slots=True)
class PortMixFixture:
    slot_port_distances_m: tuple[tuple[Fraction, ...], ...]
    sku_port_moves: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        require_tuple(self.slot_port_distances_m, "distances")
        require_tuple(self.sku_port_moves, "moves")
        if not self.slot_port_distances_m or not self.sku_port_moves:
            raise ValueError("distances and moves require nonempty rows")
        ports = len(self.slot_port_distances_m[0])
        if ports == 0 or len(self.sku_port_moves) > len(self.slot_port_distances_m):
            raise ValueError("fixture requires ports and enough distinct slots")
        for row in self.slot_port_distances_m:
            require_tuple(row, "distance row")
            if len(row) != ports:
                raise ValueError("distance rows must refer to the same ports")
            for distance in row:
                require_rational(distance, "distance", allow_zero=True)
        for moves in self.sku_port_moves:
            require_tuple(moves, "move row")
            if len(moves) != ports:
                raise ValueError("move rows must refer to the same ports")
            for count in moves:
                require_count(count, "moves", allow_zero=True)


@dataclass(frozen=True, slots=True)
class PlacementComparison:
    baseline_m: Fraction
    candidate_m: Fraction
    source_kind: Literal["analytical_fixture"] = field(init=False, default="analytical_fixture")
    metric: Literal["weighted_route_metres"] = field(init=False, default="weighted_route_metres")

    @property
    def candidate_minus_baseline_m(self) -> Fraction:
        return self.candidate_m - self.baseline_m


def score_placement(fixture: PortMixFixture, placement: tuple[int, ...]) -> Fraction:
    require_tuple(placement, "placement")
    if len(placement) != len(fixture.sku_port_moves):
        raise ValueError("placement must assign every SKU once")
    for slot in placement:
        require_count(slot, "slot index", allow_zero=True)
        if slot >= len(fixture.slot_port_distances_m):
            raise ValueError("unknown fixture slot")
    if len(set(placement)) != len(placement):
        raise ValueError("fixture permits one SKU per slot")
    total = Fraction()
    for sku, slot in enumerate(placement):
        for distance, moves in zip(
            fixture.slot_port_distances_m[slot], fixture.sku_port_moves[sku], strict=True
        ):
            total += distance * moves
    return total


def compare_placements(
    fixture: PortMixFixture, baseline: tuple[int, ...], candidate: tuple[int, ...]
) -> PlacementComparison:
    """Both placements use exactly one immutable exogenous input object."""
    return PlacementComparison(
        score_placement(fixture, baseline), score_placement(fixture, candidate)
    )
