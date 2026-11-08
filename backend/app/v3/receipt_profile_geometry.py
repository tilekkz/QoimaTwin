"""Bind declared staging cells through the existing exact source-clearance checks."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from app.v3.flow_profile_decode import rational
from app.v3.input_models import V3Bundle
from app.v3.profile_connectors import add_connectors
from app.v3.profile_models import BufferChoice
from app.v3.receipt_flow_models import ReceiptPlace


@dataclass(frozen=True, slots=True)
class _Connectors:
    proposal_id: str
    buffers: tuple[BufferChoice, ...]


def _decimal(value: Fraction) -> str:
    denominator, scale = value.denominator, 0
    for factor in (2, 5):
        count = 0
        while denominator % factor == 0:
            denominator //= factor
            count += 1
        scale = max(scale, count)
    if denominator != 1:
        raise ValueError("Receipt connector requires exactly finite source JSON decimals")
    if scale == 0:
        return str(value.numerator)
    digits = str(abs(value.numerator) * (10**scale // value.denominator)).zfill(scale + 1)
    return ("-" if value < 0 else "") + digits[:-scale] + "." + digits[-scale:]


def _buffer(row: dict[str, Any]) -> BufferChoice:
    bounds = [_decimal(rational(value)) for value in row["bounds_xz"]]
    return BufferChoice(
        place_id=row["owner_id"],
        port_id=row["port_id"],
        zone_id=row["zone_id"],
        bounds_xz=(bounds[0], bounds[1], bounds[2], bounds[3]),
        path_xz=tuple((_decimal(rational(x)), _decimal(rational(z))) for x, z in row["path_xz"]),
        height_m=_decimal(rational(row["height_m"])),
        max_payload_kg=_decimal(rational(row["max_gross_kg"])),
    )


def bind_buffers(
    bundle: V3Bundle, document: dict[str, Any], links: Any
) -> tuple[ReceiptPlace, ...]:
    rows = sorted(document["receipt_buffers"], key=lambda row: row["owner_id"])
    choices = _Connectors(document["profile_id"], tuple(_buffer(row) for row in rows))
    original_count = len(links["walk_graph"]["arcs"])
    resolved = add_connectors(bundle, choices, links)
    for arc in links["walk_graph"]["arcs"][original_count:]:
        arc["allowed_cargo_archetype_ids"] = ["SMALL_CARTON"]
        arc["cargo_transport_supported"] = True
        arc["source"] = "backend:ADR0052"
    links["connector_provenance"]["cargo_classes"] = ["SMALL_CARTON"]
    by_id = {row["owner_id"]: row for row in rows}
    return tuple(
        ReceiptPlace(
            place.place_id,
            place.node_id,
            place.usable_dimensions_xyz_m,
            place.max_payload_kg,
            rational(by_id[place.place_id]["clearance_m"]),
        )
        for _, place in resolved
    )
