"""Layout contract `qoima-72x48-v2` (contracts/layout.example.json)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, PositiveFloat, PositiveInt

from app.contracts.base import FrozenModel, NonEmptyStr, Vec3


class Units(FrozenModel):
    length: Literal["m"]
    time: Literal["s"]
    up_axis: Literal["Y"]
    handedness: Literal["right"]


class Box(FrozenModel):
    min: Vec3
    max: Vec3


class Zone(FrozenModel):
    zone_id: NonEmptyStr
    min: Vec3
    max: Vec3


class GraphNode(FrozenModel):
    node_id: NonEmptyStr
    pos: Vec3


class GraphEdge(FrozenModel):
    a: NonEmptyStr
    b: NonEmptyStr
    length_m: PositiveFloat


class Graph(FrozenModel):
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


class ForkliftGraphs(FrozenModel):
    inbound: Graph
    outbound: Graph


class Rack(FrozenModel):
    rack_id: NonEmptyStr
    root: Vec3
    size: Vec3


class Slot(FrozenModel):
    slot_id: NonEmptyStr
    rack_id: NonEmptyStr
    level: Literal[1, 2, 3]
    kind: Literal["pickface", "reserve"]
    service_node_id: NonEmptyStr | None
    bin_anchor: Vec3


class Induction(FrozenModel):
    induction_id: NonEmptyStr
    home_node_id: NonEmptyStr
    feed_segment_id: NonEmptyStr
    handoff_anchor: Vec3


class PackStation(FrozenModel):
    pack_id: NonEmptyStr
    worker_pos: Vec3
    input_segment_id: NonEmptyStr
    output_segment_id: NonEmptyStr
    buffer_capacity: PositiveInt
    input_anchor: Vec3
    output_anchor: Vec3


class Segment(FrozenModel):
    segment_id: NonEmptyStr
    start: Vec3 = Field(alias="from")
    end: Vec3 = Field(alias="to")
    length_m: PositiveFloat
    cell_length_m: PositiveFloat
    cell_count: PositiveInt
    role: Literal["tote", "parcel"]


class Connection(FrozenModel):
    from_segment_id: NonEmptyStr
    to_segment_id: NonEmptyStr
    at: Vec3


class Terminal(FrozenModel):
    segment_id: NonEmptyStr
    shipping_buffer_pos: Vec3


class Conveyor(FrozenModel):
    cell_length_m: PositiveFloat
    loop_length_m: PositiveFloat
    total_cell_count: PositiveInt
    segments: tuple[Segment, ...]
    connections: tuple[Connection, ...]
    terminal: Terminal


class Counts(FrozenModel):
    racks: int
    slots: int
    pickfaces: int
    reserve_slots: int
    picker_nodes: int
    picker_edges: int


class Layout(FrozenModel):
    schema_version: Literal["2.0"]
    layout_version: NonEmptyStr
    units: Units
    bounds: Box
    zones: tuple[Zone, ...]
    picker_graph: Graph
    forklift_graphs: ForkliftGraphs
    racks: tuple[Rack, ...]
    slots: tuple[Slot, ...]
    inductions: tuple[Induction, ...]
    pack_stations: tuple[PackStation, ...]
    relocation_home_node_id: NonEmptyStr
    relocation_buffer_node_id: NonEmptyStr
    conveyor: Conveyor
    counts: Counts
