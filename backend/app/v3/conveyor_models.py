"""Frozen static conveyor values; resource requirements are never live grants."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from app.v3.input_models import ImmutableDocument

Point = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class ConveyorNode:
    node_id: str
    position: Point
    kind: str


@dataclass(frozen=True, slots=True)
class ConveyorArc:
    centre: Point
    radius_m: Fraction
    theta_start_rad: Fraction
    theta_end_rad: Fraction


@dataclass(frozen=True, slots=True)
class ConveyorEdge:
    edge_id: str
    source: str
    target: str
    resource_id: str
    length_m: Fraction
    path_kind: str
    dwell_s: Fraction
    turn_node_id: str | None
    turn_timing: str | None
    arc: ConveyorArc | None


@dataclass(frozen=True, slots=True)
class ConveyorCell:
    cell_id: str
    position: Point | None
    length_m: Fraction | None
    resource_id: str
    capacity: int
    theta_range: tuple[Fraction, Fraction] | None


@dataclass(frozen=True, slots=True)
class ConveyorResource:
    resource_id: str
    capacity: int
    cell_ids: tuple[str, ...]
    exclusive: bool


@dataclass(frozen=True, slots=True)
class ConveyorStation:
    station_id: str
    work_node_id: str
    spur_resource_id: str


@dataclass(frozen=True, slots=True)
class ConveyorSource:
    source_revision: str
    raw_sha256: str
    document_sha256: str
    document: ImmutableDocument
    nodes: Mapping[str, ConveyorNode]
    edges: Mapping[str, ConveyorEdge]
    cells: Mapping[str, ConveyorCell]
    resources: Mapping[str, ConveyorResource]
    stations: Mapping[str, ConveyorStation]
    module_count: int
    speed_m_s: Fraction
    max_gross_kg: Fraction
    max_footprint_m: tuple[Fraction, Fraction]
    max_height_m: Fraction
    clearance_m: Fraction
    usable_width_m: Fraction
    allowed_kinds: tuple[str, ...]

    def reachable(self, start: str, end: str) -> bool:
        if start not in self.nodes or end not in self.nodes:
            raise ValueError("Unknown conveyor node")
        pending, visited = [start], set[str]()
        while pending:
            current = pending.pop()
            if current == end:
                return True
            if current not in visited:
                visited.add(current)
                pending.extend(e.target for e in self.edges.values() if e.source == current)
        return False


@dataclass(frozen=True, slots=True)
class ConveyorPayload:
    payload_id: str
    kind: str
    dimensions_xyz_m: Point
    gross_mass_kg: Fraction
    orientation: str
    parent_id: str
    source_id: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(s, str) and s.strip()
            for s in (self.payload_id, self.kind, self.orientation, self.parent_id, self.source_id)
        ):
            raise ValueError("Explicit payload identities and orientation are required")
        values = (*self.dimensions_xyz_m, self.gross_mass_kg)
        if len(self.dimensions_xyz_m) != 3 or any(
            not isinstance(v, Fraction) or v <= 0 for v in values
        ):
            raise ValueError(
                "Payload dimensions and complete gross mass must be positive Fractions"
            )


@dataclass(frozen=True, slots=True)
class ConveyorAdmission:
    reasons: tuple[str, ...]
    operational_admission: bool = False

    @property
    def eligible(self) -> bool:
        return not self.reasons


@dataclass(frozen=True, slots=True)
class MotionTiming:
    motion_seconds: Fraction
    dwell_seconds: Fraction
    motion_ticks: int
    dwell_ticks: int
    turn_node_id: str | None
    turn_timing: str | None

    @property
    def total_ticks(self) -> int:
        return self.motion_ticks + self.dwell_ticks


@dataclass(frozen=True, slots=True)
class ResourceRequirements:
    cell_ids: tuple[str, ...]
    exclusive_resource_ids: tuple[str, ...]
    live_grant: bool = False
