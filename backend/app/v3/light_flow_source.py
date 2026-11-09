"""Bind source geometry/stock/port facts while preserving explicit synthetic process choices."""

from collections import deque
from dataclasses import replace
from fractions import Fraction
from typing import Any

from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import RAW_SHA256, SOURCE_PATH
from app.v3.input_models import V3Bundle
from app.v3.light_flow_models import FlowOrder, FlowPort, FlowProfile
from app.v3.runtime_graph_source import compiled_graph
from app.v3.runtime_time import operation_ticks
from app.v3.stock_source import source_seed

PREFIX = "docs/v3/contract-proposals/"


def bind_source_profile(
    bundle: V3Bundle, conveyor: ConveyorSource, choices: FlowProfile
) -> FlowProfile:
    """Template graph/stock/anchor fields are derived outputs, never user geometry overrides."""
    if conveyor.source_revision != bundle.source_revision or conveyor.raw_sha256 != RAW_SHA256:
        raise ValueError("Source flow requires the matching verified conveyor supplement")
    links = bundle.documents[PREFIX + "layout-links-v3.json"].decode()
    slots = bundle.documents[PREFIX + "storage-slots-v3.json"].decode()["slots"]
    port = next((p for p in bundle.ports if p.port_id == choices.port.port_id), None)
    if (
        port is None
        or port.direction != "outbound"
        or "SMALL_CARTON" not in dict(port.seconds_by_archetype)
    ):
        raise ValueError("Selected source port does not serve SMALL parcels")
    station = choices.station.station_id
    if station not in conveyor.stations:
        raise ValueError("Unknown source packing station")
    work = conveyor.stations[station].work_node_id
    start = conveyor.edges["v3:conv:feed"].source
    end = conveyor.edges["v3:conv:main-tail"].target
    route = _path(conveyor, start, work) + _path(conveyor, work, end)
    windows = tuple(
        (operation_ticks(Fraction(str(a))), operation_ticks(Fraction(str(b))))
        for a, b in port.open_windows
    )
    return replace(
        choices,
        graph=compiled_graph(links, "walk"),
        stock=source_seed(bundle),
        orders=tuple(_order(bundle, order, slots) for order in choices.orders),
        cart=replace(choices.cart, park="v3:service:CART_PARK"),
        station=replace(choices.station, node="v3:service:" + station),
        port=FlowPort(
            port.port_id,
            port.service_node_id,
            operation_ticks(Fraction(str(dict(port.seconds_by_archetype)["SMALL_CARTON"]))),
            windows,
        ),
        intake_node="v3:service:CONVEYOR_IN",
        output_node="v3:service:CONVEYOR_OUT",
        belt_route=route,
        source_revision=bundle.source_revision,
        source_hashes=(
            *((s.path, s.raw_sha256) for s in bundle.source_inventory),
            (SOURCE_PATH, conveyor.raw_sha256),
        ),
    )


def _order(bundle: V3Bundle, order: FlowOrder, slots: list[dict[str, Any]]) -> FlowOrder:
    hu = next((h for h in bundle.handling_units if h.handling_unit_id == order.source_hu), None)
    if hu is None or hu.archetype_id != "SMALL_CARTON":
        raise ValueError("Source light picking requires an original SMALL HU")
    slot = next(row for row in slots if row["slot_id"] == hu.slot_id)
    if slot["reserve_only"] or slot["retrieval_blocked"] or not slot["manual_pick_allowed"]:
        raise ValueError("Source slot is not manually retrievable")
    return replace(
        order, source_node=slot["service_node_id"], cart_source_node=slot["access"]["cart_stop_id"]
    )


def _path(source: ConveyorSource, start: str, end: str) -> tuple[str, ...]:
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(start, ())])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if node == end:
            return path
        for edge in sorted(source.edges.values(), key=lambda e: e.edge_id):
            if edge.source == node and edge.target not in seen:
                seen.add(edge.target)
                queue.append((edge.target, (*path, edge.edge_id)))
    raise ValueError("Source has no directed intake/station/output route")
