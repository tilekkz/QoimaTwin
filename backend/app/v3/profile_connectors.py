"""Extend a copy of compiled source geometry with declared, checked local paths."""

from fractions import Fraction
from itertools import pairwise
from typing import Any

from app.v3.execution_types import PlaceSpec
from app.v3.input_models import V3Bundle
from app.v3.materialize import number
from app.v3.profile_build import dimensions, document
from app.v3.profile_geometry import rectangle, validate_buffer_separation, validate_connector
from app.v3.profile_models import BufferChoice, ManualProposal


def _source_cell(choice: BufferChoice, source_ports: Any) -> None:
    rows = [p for p in source_ports["ports"] if p["port_id"] == choice.port_id]
    if not rows:
        raise ValueError("unknown buffer port")
    port = rows[0]
    allocations = port["finite_buffer_capacity"]["allocations"]
    if choice.zone_id not in {a["zone_id"] for a in allocations}:
        raise ValueError("buffer zone is not allocated to this port")
    if port["direction"] == "outbound":
        cells = port["finite_buffer_capacity"]["buffer_cells"]
        matches = [c for c in cells if c["cell_id"] == choice.place_id]
        bounds = tuple(number(v, positive=False) for v in choice.bounds_xz)
        if len(matches) != 1 or rectangle(matches[0]["floor_bounds_xz_m"]) != bounds:
            raise ValueError("outbound buffer must preserve actual source cell bounds")


def _append_path(graph: Any, choice: BufferChoice, points: Any, service_id: str) -> str:
    previous = service_id
    for index, (a, b) in enumerate(pairwise(points)):
        node = f"synthetic:{choice.place_id}:point:{index}"
        graph["nodes"].append(
            {
                "node_id": node,
                "world_pos": [_json_number(b[0]), 0, _json_number(b[1])],
                "source": "backend:ADR0032",
                "synthetic": True,
            }
        )
        length = abs(b[0] - a[0]) + abs(b[1] - a[1])
        for suffix, source, target in (("f", previous, node), ("r", node, previous)):
            graph["arcs"].append(
                {
                    "arc_id": f"{node}:{suffix}",
                    "from_node_id": source,
                    "to_node_id": target,
                    "length_m": _json_number(length),
                    "cost_m": _json_number(length),
                    "width_m": 0.8,
                    "clear_height_m": 2.2,
                    "allowed_modes": ["pedestrian"],
                    "source": "backend:ADR0032",
                    "source_route_id": choice.place_id,
                    "synthetic": True,
                }
            )
        previous = node
    return previous


def _json_number(value: Fraction) -> float:
    result = float(value)
    if Fraction(str(result)) != value:
        raise ValueError("connector precision cannot be preserved in compiled JSON numbers")
    return result


def add_connectors(
    bundle: V3Bundle, proposal: ManualProposal, links: Any
) -> tuple[tuple[str, PlaceSpec], ...]:
    zones = document(bundle, "layout-v3.zones.json")
    modules = document(bundle, "storage-slots-v3.json")
    source_ports = {d: document(bundle, f"ports-v3.{d}.json") for d in ("inbound", "outbound")}
    ports = {p.port_id: p for p in bundle.ports}
    nodes = {n["node_id"]: n["world_pos"] for n in links["walk_graph"]["nodes"]}
    result = []
    if len({c.place_id for c in proposal.buffers}) != len(proposal.buffers):
        raise ValueError("duplicate finite buffer place")
    validate_buffer_separation(proposal.buffers)
    links["connector_provenance"] = {
        "classification": "explicit_synthetic_local_geometry",
        "proposal_id": proposal.proposal_id,
        "swept_radius_m": "0.4",
        "clear_height_m": "2.2",
        "buffers": [c.model_dump() for c in proposal.buffers],
    }
    for choice in proposal.buffers:
        if choice.port_id not in ports:
            raise ValueError("unknown buffer port")
        port = ports[choice.port_id]
        _source_cell(choice, source_ports[port.direction])
        position = nodes[port.service_node_id]
        service = Fraction(str(position[0])), Fraction(str(position[2]))
        points = validate_connector(choice, zones, modules, service)
        node = _append_path(links["walk_graph"], choice, points, port.service_node_id)
        x0, z0, x1, z1 = (number(v, positive=False) for v in choice.bounds_xz)
        place = PlaceSpec(
            choice.place_id,
            node,
            dimensions((x1 - x0, number(choice.height_m), z1 - z0)),
            number(choice.max_payload_kg),
            frozenset({"SMALL_CARTON", "STANDARD_CARTON"}),
        )
        result.append((port.port_id, place))
    return tuple(result)
