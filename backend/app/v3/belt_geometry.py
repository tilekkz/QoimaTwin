"""Source-cell footprint overlap, including a bounded exact rational arc enclosure."""

from fractions import Fraction as F
from functools import lru_cache

from app.v3.belt_models import BeltPose
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource


def angular_halfspan(source: ConveyorSource, payload: ConveyorPayload) -> F:
    arc = source.edges["v3:conv:entry-arc"].arc
    if arc is None:
        raise ValueError("Missing source arc geometry")
    width, _, depth = payload.dimensions_xyz_m
    radius, clearance = arc.radius_m, source.clearance_m
    inside = radius - source.usable_width_m / 2 + clearance
    outside = radius + source.usable_width_m / 2 - clearance
    if radius - width / 2 < inside or (radius + width / 2) ** 2 + (depth / 2) ** 2 > outside**2:
        raise ValueError("CURVE_ANNULUS_MISMATCH")
    return atan_upper(depth / (2 * radius - width))


@lru_cache(maxsize=128)
def atan_upper(value: F) -> F:
    """Alternating-series upper bound, rounded outward to1e-18rad; no float epsilon."""
    if not 0 < value <= F(1, 4):
        raise ValueError("Unsupported arc angular ratio")
    # 25 terms end with a positive term: exact upper bound for atan on(0,1).
    upper = sum(((-1) ** n * value ** (2 * n + 1) / (2 * n + 1) for n in range(25)), F(0))
    scale = 10**18
    scaled = upper * scale
    return F(-(-scaled.numerator // scaled.denominator), scale)


def coordinates(source: ConveyorSource, pose: BeltPose) -> tuple[F, F]:
    edge = source.edges[pose.edge_id]
    if edge.arc is not None:
        raise ValueError("Arc pose uses source theta/progress, not invented Cartesian fractions")
    start, end = source.nodes[edge.source].position, source.nodes[edge.target].position
    return (
        start[0] + (end[0] - start[0]) * pose.progress,
        start[2] + (end[2] - start[2]) * pose.progress,
    )


def rectangle(source: ConveyorSource, cell_id: str) -> tuple[F, F, F, F]:
    cell = source.cells[cell_id]
    if cell.position is None or cell.length_m is None:
        raise ValueError("Angular cell has no Cartesian rectangle")
    x, _, z = cell.position
    resource = cell.resource_id
    if resource.startswith("V3_T"):
        half_x = half_z = cell.length_m / 2
    elif resource == "V3_MAIN":
        half_x, half_z = cell.length_m / 2, source.usable_width_m / 2
    else:
        half_x, half_z = source.usable_width_m / 2, cell.length_m / 2
    return x - half_x, x + half_x, z - half_z, z + half_z


def footprint(source: ConveyorSource, payload: ConveyorPayload, pose: BeltPose) -> frozenset[str]:
    edge = source.edges[pose.edge_id]
    if edge.arc is not None:
        return arc_cells(source, payload, pose)
    x, z = coordinates(source, pose)
    if pose.yaw_quarters.denominator != 1:
        pivot_cells = [
            c.cell_id
            for c in source.cells.values()
            if c.position is not None
            and c.position[0] == x
            and c.position[2] == z
            and c.resource_id.startswith("V3_T")
        ]
        if len(pivot_cells) != 1:
            raise ValueError("Stopped pivot requires source T centre")
        return frozenset(pivot_cells)
    width, _, depth = payload.dimensions_xyz_m
    half_x, half_z = (
        (width / 2, depth / 2) if pose.yaw_quarters % 2 == 0 else (depth / 2, width / 2)
    )
    cells = set[str]()
    for cell in source.cells.values():
        if cell.position is None:
            continue
        left, right, bottom, top = rectangle(source, cell.cell_id)
        if x + half_x > left and x - half_x < right and z + half_z > bottom and z - half_z < top:
            cells.add(cell.cell_id)
    curve = source.edges["v3:conv:entry-arc"]
    entry = source.nodes[curve.source].position
    exit_point = source.nodes[curve.target].position
    if edge.resource_id == "V3_FEED" and z - half_z < entry[2]:
        cells.add("V3-C-ARC-00")
    if edge.resource_id == "V3_MAIN" and x + half_x > exit_point[0]:
        cells.add("V3-C-ARC-03")
    return frozenset(cells)


def arc_cells(source: ConveyorSource, payload: ConveyorPayload, pose: BeltPose) -> frozenset[str]:
    arc = source.edges[pose.edge_id].arc
    if arc is None:
        raise ValueError("Expected source arc")
    theta = arc.theta_start_rad + (arc.theta_end_rad - arc.theta_start_rad) * pose.progress
    half = angular_halfspan(source, payload)
    cells = {
        c.cell_id
        for c in source.cells.values()
        if c.theta_range is not None
        and theta + half > c.theta_range[1]
        and theta - half < c.theta_range[0]
    }
    if theta + half > arc.theta_start_rad:
        cells.add("V3-C-FEED")
    if theta - half < arc.theta_end_rad:
        cells.add("V3-C-MAIN-000")
    return frozenset(cells)


def requirements(source: ConveyorSource, cells: frozenset[str]) -> frozenset[str]:
    result = {"cell:" + cell for cell in cells}
    result.update(
        "resource:" + source.cells[c].resource_id
        for c in cells
        if source.resources[source.cells[c].resource_id].exclusive
    )
    return frozenset(result)
