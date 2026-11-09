"""Necessary exact static checks only; no actual geometry or operation certificate."""

from decimal import Decimal
from fractions import Fraction as F
from typing import Literal

from app.v3.admission_models import Handler
from app.v3.admission_source import SelectedCapability, SourceAdmissionCatalog
from app.v3.long_freight_models import LongFreightRequest, LongFreightStatic
from app.v3.long_freight_source import LongFreightSource
from app.v3.vehicle_admission import check_handling_prerequisites
from app.v3.vehicle_evidence import HandlingRequest
from app.v3.vehicle_handling import LoadDesign


def straight_gate_fits(envelope: tuple[F, F], gate: tuple[F, F], clearance: F) -> bool:
    """Hand-only straight aligned envelope test, never a signed source route proof."""
    if type(envelope) is not tuple or type(gate) is not tuple:
        raise ValueError("EXACT_GATE_TUPLES_REQUIRED")
    if len(envelope) != 2 or len(gate) != 2:
        raise ValueError("GATE_WIDTH_HEIGHT_REQUIRED")
    if any(type(v) is not F or v <= 0 for v in (*envelope, *gate)):
        raise ValueError("EXACT_POSITIVE_GATE_FRACTIONS_REQUIRED")
    if type(clearance) is not F or clearance < 0:
        raise ValueError("EXACT_NONNEGATIVE_GATE_CLEARANCE_REQUIRED")
    return all(size + 2 * clearance <= room for size, room in zip(envelope, gate, strict=True))


def _capability(source: LongFreightSource) -> SelectedCapability:
    limits = source.vehicles.handling.limits
    return SelectedCapability(
        Handler(
            "forklift_operator",
            ("LONG_BUNDLE",),
            Decimal(limits.nominal_kg.numerator) / Decimal(limits.nominal_kg.denominator),
            Decimal(limits.maximum_fork_y_m.numerator)
            / Decimal(limits.maximum_fork_y_m.denominator),
        ),
        "forklift_assisted",
        frozenset({"forklift", "approved_load_support"}),
    )


def _request_reasons(source: LongFreightSource, request: LongFreightRequest) -> list[str]:
    reasons = []
    if request.orientation_id != source.original.orientation_id:
        reasons.append("ORIENTATION_FORBIDDEN")
    if request.target_slot_id == request.source_slot_id:
        reasons.append("TARGET_EQUALS_SOURCE")
    if request.target_slot_id != "v3:slot:LONG_W:001:L1:B1":
        reasons.append("TARGET_OUT_OF_SCOPE")
    if any(h.slot_id == request.target_slot_id for h in source.bundle.handling_units):
        reasons.append("TARGET_OCCUPIED")
    pair = request.pair_id, request.actor_id, request.vehicle_id
    if (
        pair != ("OUTBOUND_FORKLIFT_PAIR", "F02", "FL02")
        or pair not in source.vehicles.handling.pairs
    ):
        reasons.append("FIXED_OUTBOUND_PAIR_REQUIRED")
    port = next(p for p in source.bundle.ports if p.port_id == request.port_id)
    if port.direction != "outbound" or "LONG_BUNDLE" not in port.allowed_cargo_archetype_ids:
        reasons.append("PORT_CARGO_FORBIDDEN")
    return reasons


def _design(
    source: LongFreightSource,
    request: LongFreightRequest,
    load: LoadDesign,
    slot_id: str,
    action: Literal["pickup", "place"],
) -> bool:
    slot = next(s for s in source.vehicles.handling.slots if s.slot_id == slot_id)
    value = HandlingRequest(
        request.hu_id,
        "LONG_BUNDLE",
        request.pair_id,
        request.port_id,
        slot_id,
        action,
        load.dimensions_m,
        load.hu_mass_kg,
        slot.support_y_m - load.support_to_fork_offset_m,
        (),
    )
    return check_handling_prerequisites(
        source.vehicles.handling,
        value,
        source.vehicles.source_hashes,
    ).design_passed


def _port_values(source: LongFreightSource, port_id: str) -> tuple[F, F, F | None]:
    rows = source.bundle.documents["docs/v3/contract-proposals/ports-v3.outbound.json"].decode()
    port = next((r for r in rows["ports"] if r["port_id"] == port_id), None)
    if port is None:
        rows = source.bundle.documents["docs/v3/contract-proposals/ports-v3.inbound.json"].decode()
        port = next(r for r in rows["ports"] if r["port_id"] == port_id)
    seconds = port["service_time_rule"]["seconds_by_archetype"].get("LONG_BUNDLE")
    return (
        F(str(port["clear_width_m"])),
        F(str(port["clear_height_m"])),
        None if seconds is None else F(str(seconds)),
    )


def static_checks(source: LongFreightSource, request: LongFreightRequest) -> LongFreightStatic:
    catalog = SourceAdmissionCatalog.from_bundle(source.bundle)
    load = next(v for v in source.vehicles.handling.loads if v.cargo_id == "LONG_BUNDLE")
    target = catalog.slots[request.target_slot_id].slot
    reasons = _request_reasons(source, request)
    admission = catalog.evaluate(
        request.hu_id, request.target_slot_id, _capability(source), placements=catalog.baseline
    )
    reasons.extend(admission.reasons)
    pickup = _design(source, request, load, request.source_slot_id, "pickup")
    place = _design(source, request, load, request.target_slot_id, "place")
    if not pickup:
        reasons.append("PICKUP_C08_DESIGN_MISMATCH")
    if not place:
        reasons.append("PLACE_C08_DESIGN_MISMATCH")
    width, height, seconds = _port_values(source, request.port_id)
    dimensions = tuple(F(v) for v in target.dimensions)
    required = tuple(v + 2 * F(target.clearance_m) for v in load.dimensions_m)
    return LongFreightStatic(
        "static_rejected" if reasons else "prerequisites_only",
        tuple(dict.fromkeys(reasons)),
        (required[0], required[1], required[2]),
        (dimensions[0], dimensions[1], dimensions[2]),
        load.hu_mass_kg,
        load.attachment_mass_kg,
        load.hu_mass_kg + load.attachment_mass_kg,
        width,
        height,
        seconds,
        pickup,
        place,
    )
