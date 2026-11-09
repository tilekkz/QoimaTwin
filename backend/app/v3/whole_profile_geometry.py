"""Exact declared local connectors are checked before adding manual cargo permissions."""

from dataclasses import dataclass
from typing import Any

from app.v3.input_models import V3Bundle
from app.v3.profile_connectors import add_connectors
from app.v3.profile_models import BufferChoice
from app.v3.receipt_flow_models import ReceiptPlace, ReceiptPort
from app.v3.stock_validation import exact
from app.v3.whole_flow_models import WholeFlowProfile, WholeHUPort

ROUTE_POLICY = "c09-manual-small-standard-source-mode-projection-v1"


def project_whole_manual_cargo(links: dict[str, Any]) -> None:
    """Only a fresh decode of verified pinned source is accepted by the public binder."""
    for arc in links["walk_graph"]["arcs"]:
        if (
            "pedestrian" in arc.get("allowed_modes", [])
            and "allowed_cargo_archetype_ids" not in arc
            and "cargo_transport_supported" not in arc
        ):
            arc["allowed_cargo_archetype_ids"] = ["SMALL_CARTON", "STANDARD_CARTON"]
            arc["cargo_transport_supported"] = True


@dataclass(frozen=True, slots=True)
class _Connectors:
    proposal_id: str
    buffers: tuple[BufferChoice, ...]


def bind_buffers(
    bundle: V3Bundle,
    profile: WholeFlowProfile,
    buffers: tuple[BufferChoice, ...],
    links: dict[str, Any],
) -> dict[str, ReceiptPlace]:
    if type(buffers) is not tuple or any(type(b) is not BufferChoice for b in buffers):
        raise ValueError("Exact immutable typed local buffer choices required")
    declared = {p.owner_id: p for p in (*profile.receipts.places, *profile.places)}
    selected = {}
    ports: tuple[ReceiptPort | WholeHUPort, ...] = (*profile.receipts.ports, *profile.ports)
    for port in ports:
        for key in port.buffer_ids:
            if key in selected:
                raise ValueError("One buffer cannot belong to multiple source ports")
            selected[key] = port.port_id
    if {b.place_id: b.port_id for b in buffers} != selected:
        raise ValueError("Every source buffer must have exactly one explicit connector")
    if any(b.place_id not in declared for b in buffers):
        raise ValueError("Every buffer requires explicit exact clearance")
    before = len(links["walk_graph"]["arcs"])
    result = add_connectors(bundle, _Connectors(profile.receipts.flow.profile_id, buffers), links)
    for arc in links["walk_graph"]["arcs"][before:]:
        arc["allowed_cargo_archetype_ids"] = ["SMALL_CARTON", "STANDARD_CARTON"]
        arc["cargo_transport_supported"] = True
        arc["source"] = "backend:ADR0056"
    links["connector_provenance"]["cargo_classes"] = ["SMALL_CARTON", "STANDARD_CARTON"]
    places = {}
    for _, place in result:
        margin = declared[place.place_id].clearance_m
        exact(margin)
        places[place.place_id] = ReceiptPlace(
            place.place_id,
            place.node_id,
            place.usable_dimensions_xyz_m,
            place.max_payload_kg,
            margin,
        )
    return places
