"""F2 hypothetical identical-box grid packing; not production cargo admission."""

from dataclasses import dataclass, field
from fractions import Fraction
from math import prod
from typing import Literal

from app.v3.analytical_common import require_count, require_rational, require_tuple

type Dimensions = tuple[Fraction, Fraction, Fraction]
type AxisOrder = tuple[int, int, int]
type FitReason = Literal[
    "DESIGN_COMPATIBLE",
    "DIMENSION_MISMATCH",
    "OVERWEIGHT",
    "ORIENTATION_FORBIDDEN",
    "SLOT_CAPACITY",
]
AXIS_ORDERS: tuple[AxisOrder, ...] = (
    (0, 1, 2),
    (0, 2, 1),
    (1, 0, 2),
    (1, 2, 0),
    (2, 0, 1),
    (2, 1, 0),
)


def _dimensions(values: Dimensions) -> None:
    require_tuple(values, "dimensions")
    if len(values) != 3:
        raise ValueError("dimensions require three axes")
    for value in values:
        require_rational(value, "dimension")


@dataclass(frozen=True, slots=True)
class BoxFixture:
    dimensions_m: Dimensions
    gross_mass_kg: Fraction

    def __post_init__(self) -> None:
        _dimensions(self.dimensions_m)
        require_rational(self.gross_mass_kg, "gross mass")


@dataclass(frozen=True, slots=True)
class SlotFixture:
    usable_m: Dimensions
    payload_kg: Fraction

    def __post_init__(self) -> None:
        _dimensions(self.usable_m)
        require_rational(self.payload_kg, "payload")


@dataclass(frozen=True, slots=True)
class FixtureFit:
    reason: FitReason
    orientation: AxisOrder | None
    geometric_capacity: int
    gross_mass_kg: Fraction
    source_kind: Literal["analytical_fixture"] = field(init=False, default="analytical_fixture")

    @property
    def accepted(self) -> bool:
        return self.reason == "DESIGN_COMPATIBLE"


def _capacities(
    box: BoxFixture, slot: SlotFixture, orientations: tuple[AxisOrder, ...]
) -> list[tuple[int, AxisOrder]]:
    require_tuple(orientations, "orientations")
    result: list[tuple[int, AxisOrder]] = []
    for order in orientations:
        require_tuple(order, "axis order")
        if any(type(axis) is not int for axis in order) or sorted(order) != [0, 1, 2]:
            raise ValueError("orientation must be a permutation of the three axes")
        capacity = prod(slot.usable_m[i] // box.dimensions_m[axis] for i, axis in enumerate(order))
        result.append((capacity, order))
    return sorted(result, key=lambda item: (-item[0], item[1]))


def evaluate_fixture_fit(
    box: BoxFixture,
    slot: SlotFixture,
    quantity: int = 1,
    *,
    orientations: tuple[AxisOrder, ...] = AXIS_ORDERS,
) -> FixtureFit:
    """Uniform axis-aligned grid, zero clearance, no mixed rotations or arbitrary tilting."""
    require_count(quantity, "quantity")
    candidates = _capacities(box, slot, orientations)
    mass = quantity * box.gross_mass_kg
    if not candidates:
        return FixtureFit("ORIENTATION_FORBIDDEN", None, 0, mass)
    capacity, orientation = candidates[0]
    if capacity == 0:
        return FixtureFit("DIMENSION_MISMATCH", None, 0, mass)
    if quantity > capacity:
        return FixtureFit("SLOT_CAPACITY", orientation, capacity, mass)
    if mass > slot.payload_kg:
        return FixtureFit("OVERWEIGHT", orientation, capacity, mass)
    return FixtureFit("DESIGN_COMPATIBLE", orientation, capacity, mass)
