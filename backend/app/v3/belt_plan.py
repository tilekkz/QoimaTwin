"""Compile explicit source routes to positive, footprint-sized checkpoint motions."""

from dataclasses import replace
from fractions import Fraction as F
from itertools import pairwise

from app.v3.belt_geometry import angular_halfspan, footprint, rectangle, requirements
from app.v3.belt_models import BeltJob, BeltPose, BeltStep
from app.v3.conveyor_models import ConveyorEdge, ConveyorPayload, ConveyorSource
from app.v3.conveyor_primitives import admit_payload, edge_timing
from app.v3.runtime_time import operation_ticks


def valid_tick(value: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_job(source: ConveyorSource, job: BeltJob) -> None:
    if not all(isinstance(value, str) and value.strip() for value in (job.job_id, job.hu_id)):
        raise ValueError("Explicit job and HU identities required")
    if (
        not isinstance(job.route, tuple)
        or not job.route
        or any(not isinstance(e, str) for e in job.route)
    ):
        raise ValueError("Explicit job, HU and route are required")
    if not isinstance(job.payload.dimensions_xyz_m, tuple):
        raise ValueError("Payload dimensions must be immutable")
    if not valid_tick(job.arrival_tick) or not valid_tick(job.station_dwell_tick):
        raise ValueError("Explicit nonnegative integer clocks required")
    if not admit_payload(source, job.payload).eligible:
        raise ValueError("Payload violates source conveyor policy")
    if any(identity not in source.edges for identity in job.route):
        raise ValueError("Unknown directed source edge; no fallback")
    edges = [source.edges[key] for key in job.route]
    if any(a.target != b.source for a, b in pairwise(edges)):
        raise ValueError("Disconnected directed route")
    visited = [
        s.station_id
        for s in source.stations.values()
        for edge in edges
        if edge.target == s.work_node_id
    ]
    if job.station_id is None:
        if visited or job.station_dwell_tick:
            raise ValueError("Station work requires explicit station and dwell")
    elif visited != [job.station_id] or job.station_id not in source.stations:
        raise ValueError("Route must visit declared station exactly once")


def motion_yaw(edge: ConveyorEdge) -> F:
    if edge.arc is not None or edge.resource_id == "V3_FEED":
        return F(0)
    if edge.resource_id.startswith("V3_SPUR") or edge.turn_timing is not None:
        return F(2)
    return F(1)


def linear_breaks(source: ConveyorSource, payload: ConveyorPayload, edge: ConveyorEdge) -> set[F]:
    start, end = source.nodes[edge.source].position, source.nodes[edge.target].position
    moving = [axis for axis in (0, 2) if start[axis] != end[axis]]
    if len(moving) != 1:
        raise ValueError("Only axis-aligned source straights are supported")
    axis = moving[0]
    width, _, depth = payload.dimensions_xyz_m
    half_x, half_z = (width / 2, depth / 2) if motion_yaw(edge) % 2 == 0 else (depth / 2, width / 2)
    longitudinal, transverse = (half_x, half_z) if axis == 0 else (half_z, half_x)
    cross = start[2 if axis == 0 else 0]
    result = {F(0), F(1)}
    for cell in source.cells.values():
        if cell.position is None:
            continue
        x0, x1, z0, z1 = rectangle(source, cell.cell_id)
        low, high, cross_low, cross_high = (x0, x1, z0, z1) if axis == 0 else (z0, z1, x0, x1)
        if cross + transverse <= cross_low or cross - transverse >= cross_high:
            continue
        for boundary in (low, high):
            for offset in (-longitudinal, longitudinal):
                progress = (boundary + offset - start[axis]) / (end[axis] - start[axis])
                if 0 < progress < 1:
                    result.add(progress)
    return result


def arc_breaks(source: ConveyorSource, payload: ConveyorPayload, edge: ConveyorEdge) -> set[F]:
    if edge.arc is None:
        raise ValueError("Missing source arc")
    arc, half = edge.arc, angular_halfspan(source, payload)
    boundaries = {
        angle
        for cell in source.cells.values()
        if cell.theta_range is not None
        for angle in cell.theta_range
    }
    result = {F(0), F(1)}
    for boundary in boundaries:
        for offset in (-half, half):
            progress = (boundary + offset - arc.theta_start_rad) / (
                arc.theta_end_rad - arc.theta_start_rad
            )
            if 0 < progress < 1:
                result.add(progress)
    return result


def pose_at(edge: ConveyorEdge, progress: F) -> BeltPose:
    return BeltPose(edge.edge_id, progress, progress if edge.arc is not None else motion_yaw(edge))


def motion_steps(source: ConveyorSource, job: BeltJob, edge: ConveyorEdge) -> list[BeltStep]:
    cuts = sorted(
        arc_breaks(source, job.payload, edge)
        if edge.arc is not None
        else linear_breaks(source, job.payload, edge)
    )
    duration = edge.length_m / source.speed_m_s
    checkpoints = {operation_ticks(duration * progress): progress for progress in cuts}
    result: list[BeltStep] = []
    previous_tick, previous = 0, F(0)
    for tick, progress in sorted(checkpoints.items()):
        if tick == 0:
            continue
        samples = [x for x in cuts if previous <= x <= progress]
        samples += [(a + b) / 2 for a, b in pairwise(samples)]
        cells = frozenset(
            c for x in samples for c in footprint(source, job.payload, pose_at(edge, x))
        )
        result.append(
            BeltStep(
                "motion",
                edge.edge_id,
                pose_at(edge, previous),
                pose_at(edge, progress),
                tick - previous_tick,
                requirements(source, cells),
            )
        )
        previous_tick, previous = tick, progress
    return result


def pivot_step(source: ConveyorSource, job: BeltJob, edge: ConveyorEdge) -> BeltStep:
    before = edge.turn_timing == "before_edge"
    progress = F(0 if before else 1)
    start, end = BeltPose(edge.edge_id, progress, F(1 if before else 2)), pose_at(edge, progress)
    if not before:
        end = replace(start, yaw_quarters=F(1))
    cells = footprint(source, job.payload, replace(start, yaw_quarters=F(3, 2)))
    return BeltStep(
        "pivot",
        edge.edge_id,
        start,
        end,
        edge_timing(source, edge.edge_id).dwell_ticks,
        requirements(source, cells),
    )


def compile_job(source: ConveyorSource, job: BeltJob) -> tuple[BeltStep, ...]:
    validate_job(source, job)
    steps: list[BeltStep] = []
    for identity in job.route:
        edge = source.edges[identity]
        if edge.turn_timing == "before_edge":
            steps.append(pivot_step(source, job, edge))
        steps.extend(motion_steps(source, job, edge))
        if edge.turn_timing == "after_edge":
            steps.append(pivot_step(source, job, edge))
        if (
            job.station_id is not None
            and edge.target == source.stations[job.station_id].work_node_id
        ):
            pose = steps[-1].end
            if job.station_dwell_tick:
                steps.append(
                    BeltStep(
                        "station",
                        identity,
                        pose,
                        pose,
                        job.station_dwell_tick,
                        requirements(source, footprint(source, job.payload, pose)),
                    )
                )
    return add_spur_guard(source, job, steps)


def add_spur_guard(
    source: ConveyorSource, job: BeltJob, steps: list[BeltStep]
) -> tuple[BeltStep, ...]:
    if job.station_id is None:
        return tuple(steps)
    station = source.stations[job.station_id]
    prefix = "v3:conv:" + job.station_id + ":"
    if prefix + "divert" not in job.route or prefix + "merge" not in job.route:
        raise ValueError("Station route requires full divert/work/return/merge")
    t_resource = source.edges[prefix + "divert"].resource_id
    first = next(i for i, step in enumerate(steps) if "resource:" + t_resource in step.resources)
    last = max(i for i, step in enumerate(steps) if step.edge_id == prefix + "merge")
    guard = frozenset(("resource:" + station.spur_resource_id,))
    return tuple(
        replace(step, resources=step.resources | guard, guards=guard)
        if first <= index <= last
        else step
        for index, step in enumerate(steps)
    )
