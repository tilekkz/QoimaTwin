"""Pure payload admission, bound-edge timing and declared-cell reservation needs."""

from app.v3.conveyor_models import (
    ConveyorAdmission,
    ConveyorPayload,
    ConveyorSource,
    MotionTiming,
    ResourceRequirements,
)
from app.v3.runtime_time import operation_ticks


def admit_payload(source: ConveyorSource, payload: ConveyorPayload) -> ConveyorAdmission:
    if payload.kind not in source.allowed_kinds:
        return ConveyorAdmission(("KIND_FORBIDDEN",))
    if payload.orientation != "upright_xyz":
        return ConveyorAdmission(("ORIENTATION_FORBIDDEN",))
    width, height, depth = payload.dimensions_xyz_m
    reasons: list[str] = []
    if width > source.max_footprint_m[0] or depth > source.max_footprint_m[1]:
        reasons.append("FOOTPRINT_MISMATCH")
    if height > source.max_height_m:
        reasons.append("HEIGHT_MISMATCH")
    if payload.gross_mass_kg > source.max_gross_kg:
        reasons.append("PAYLOAD_OVERWEIGHT")
    available = source.usable_width_m - 2 * source.clearance_m
    if width * width + depth * depth > available * available:
        reasons.append("PIVOT_CLEARANCE")
    return ConveyorAdmission(tuple(reasons))


def edge_timing(source: ConveyorSource, edge_id: str) -> MotionTiming:
    if edge_id not in source.edges:
        raise ValueError("Unknown conveyor edge")
    edge = source.edges[edge_id]
    motion = edge.length_m / source.speed_m_s
    return MotionTiming(
        motion,
        edge.dwell_s,
        operation_ticks(motion),
        operation_ticks(edge.dwell_s),
        edge.turn_node_id,
        edge.turn_timing,
    )


def edge_requirements(
    source: ConveyorSource, edge_id: str, overlapped_cell_ids: tuple[str, ...]
) -> ResourceRequirements:
    """Validate declared overlap IDs; caller must prove the footprint/swept overlap set.

    This function neither computes geometric overlap nor checks live ownership.
    Adjacent resource cells may be included at seams. Requirements are conjunctive.
    """
    if edge_id not in source.edges:
        raise ValueError("Unknown conveyor edge")
    cells = overlapped_cell_ids
    if not cells or len(set(cells)) != len(cells) or any(c not in source.cells for c in cells):
        raise ValueError("Unknown, empty or duplicated overlap cells")
    resources = {source.cells[c].resource_id for c in cells}
    if source.edges[edge_id].resource_id not in resources:
        raise ValueError("Declared cells do not cover edge resource")
    exclusive = tuple(sorted(r for r in resources if source.resources[r].exclusive))
    return ResourceRequirements(tuple(sorted(cells)), exclusive)
