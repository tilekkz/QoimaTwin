"""Fail invalid admission inputs before comparing exact physical constraints."""

from decimal import Decimal

from app.v3.admission_models import Cargo, Handler, Slot, StorageState


def _finite(values: tuple[Decimal, ...]) -> None:
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
        raise ValueError("nonfinite or non-Decimal compatibility value")


def exact_precision(cargo: Cargo, slot: Slot, state: StorageState) -> int:
    """Addition/subtraction precision independent of the caller's decimal context."""
    values = (
        *cargo.dimensions,
        *slot.dimensions,
        slot.clearance_m,
        slot.support_y_m,
        state.slot_mass_kg,
        state.module_mass_kg,
        cargo.gross_mass_kg or Decimal(0),
    )
    highest_digit = max(value.adjusted() for value in values)
    lowest_digit = min(int(value.as_tuple().exponent) for value in values)
    return max(28, highest_digit - lowest_digit + 5)


def validate_inputs(cargo: Cargo, slot: Slot, state: StorageState, handler: Handler | None) -> None:
    dimensions = (*cargo.dimensions, *slot.dimensions)
    scalars = (
        slot.max_payload_kg,
        slot.module_max_payload_kg,
        slot.clearance_m,
        slot.support_y_m,
        slot.service_height_m,
        state.slot_mass_kg,
        state.module_mass_kg,
    )
    _finite(dimensions + scalars)
    if len(cargo.dimensions) != 3 or len(slot.dimensions) != 3 or any(v <= 0 for v in dimensions):
        raise ValueError("dimensions must contain three positive values")
    if any(value < 0 for value in scalars[:5]):
        raise ValueError("negative slot limit or coordinate")
    if type(slot.max_handling_units) is not int or slot.max_handling_units < 0:
        raise ValueError("invalid slot capacity")
    if (
        type(state.slot_hus) is not int
        or state.slot_hus < 0
        or state.slot_mass_kg < 0
        or state.module_mass_kg < state.slot_mass_kg
    ):
        raise ValueError("invalid storage state")
    if (state.slot_hus == 0) != (state.slot_mass_kg == 0):
        raise ValueError("invalid storage state: count and mass disagree")
    if cargo.gross_mass_kg is not None:
        _finite((cargo.gross_mass_kg,))
        if cargo.gross_mass_kg <= 0:
            raise ValueError("cargo mass must be positive")
    if handler is not None:
        _finite((handler.max_payload_kg, handler.max_service_height_m))
        if handler.max_payload_kg <= 0 or handler.max_service_height_m < 0:
            raise ValueError("invalid handler limits")
