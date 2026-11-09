"""Exact static compatibility checks; scheduling and placement scoring remain separate."""

from decimal import localcontext

from app.v3.admission_models import (
    Admission,
    Cargo,
    Handler,
    Reason,
    RouteProof,
    Slot,
    StorageState,
)
from app.v3.admission_validation import exact_precision, validate_inputs


def _physical_reasons(cargo: Cargo, slot: Slot, state: StorageState) -> list[Reason]:
    reasons: list[Reason] = []
    if slot.reserve_only:
        return ["RESERVE_ACCESS_BLOCKED"]
    if cargo.archetype_id not in slot.allowed_archetypes:
        return ["TYPE_MISMATCH"]
    if "xyz" not in cargo.orientations or "xyz" not in slot.orientations:
        return ["ORIENTATION_FORBIDDEN"]
    if any(
        size + 2 * slot.clearance_m > space
        for size, space in zip(cargo.dimensions, slot.dimensions, strict=True)
    ):
        return ["DIMENSION_MISMATCH"]
    if cargo.gross_mass_kg is None:
        return ["UNKNOWN_MASS"]
    if state.slot_mass_kg + cargo.gross_mass_kg > slot.max_payload_kg:
        reasons.append("OVERWEIGHT")
    if state.slot_hus + 1 > slot.max_handling_units:
        reasons.append("SLOT_CAPACITY")
    if state.module_mass_kg + cargo.gross_mass_kg > slot.module_max_payload_kg:
        reasons.append("MODULE_OVERWEIGHT")
    return reasons


def _handler_reasons(cargo: Cargo, slot: Slot, handler: Handler | None) -> list[Reason]:
    if (
        handler is None
        or handler.handler_id not in slot.required_handler_ids
        or cargo.archetype_id not in handler.archetypes
        or cargo.gross_mass_kg is None
        or cargo.gross_mass_kg > handler.max_payload_kg
    ):
        return ["HANDLER_UNAVAILABLE"]
    if slot.service_height_m > handler.max_service_height_m:
        return ["HEIGHT_ACCESS_UNAVAILABLE"]
    return []


def storage_admission(
    cargo: Cargo, slot: Slot, state: StorageState, handler: Handler | None
) -> Admission:
    """Evaluate adding one whole HU; occupied-volume arrangement is a separate proof."""
    validate_inputs(cargo, slot, state, handler)
    with localcontext() as context:
        context.prec = exact_precision(cargo, slot, state)
        return _storage_result(cargo, slot, state, handler)


def _storage_result(
    cargo: Cargo, slot: Slot, state: StorageState, handler: Handler | None
) -> Admission:
    reasons = _physical_reasons(cargo, slot, state)
    if not reasons:
        reasons = _handler_reasons(cargo, slot, handler)
    if reasons:
        return Admission(tuple(reasons))
    top = slot.support_y_m + cargo.dimensions[1]
    return Admission((), slot.support_y_m, top, slot.dimensions[1] - cargo.dimensions[1])


def candidate_admission(
    cargo: Cargo,
    slot: Slot,
    state: StorageState,
    handler: Handler | None,
    route: RouteProof | None,
    layout_hash: str,
) -> Admission:
    """Compose static storage and a trusted, exact-input loaded-route proof."""
    result = storage_admission(cargo, slot, state, handler)
    if not result.eligible:
        return result
    if (
        route is None
        or not route.reachable
        or not layout_hash
        or route.layout_hash != layout_hash
        or route.cargo != cargo
        or route.slot_id != slot.slot_id
        or route.handler != handler
    ):
        return Admission(("PATH_CLEARANCE",))
    return result
