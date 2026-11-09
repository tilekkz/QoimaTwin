"""Recreate frozen execution values after wire shape checks, with exact rational quantities."""

from app.v3.execution_types import (
    ActorSpec,
    ExecutionProfile,
    HandlingTimes,
    HandlingUnit,
    HUOwner,
    InitialPlacement,
    JobView,
    Lease,
    ManualEvent,
    ManualOutcome,
    ManualSnapshot,
    Motion,
    PlaceSpec,
    PortSpec,
    SourceBinding,
    TimedJob,
    WorkerView,
)
from app.v3.interface import Json
from app.v3.run_values import fraction
from app.v3.runtime_graph import CandidateRoute


def _place(row: Json) -> PlaceSpec:
    x, y, z = (fraction(value) for value in row["usable_dimensions_xyz_m"])
    return PlaceSpec(
        row["place_id"],
        row["node_id"],
        (x, y, z),
        fraction(row["max_payload_kg"]),
        frozenset(row["allowed_archetypes"]),
    )


def _unit(row: Json) -> HandlingUnit:
    x, y, z = (fraction(value) for value in row["dimensions_xyz_m"])
    return HandlingUnit(
        row["hu_id"],
        row["sku_id"],
        row["quantity"],
        row["archetype"],
        fraction(row["gross_mass_kg"]),
        (x, y, z),
    )


def _port(row: Json) -> PortSpec:
    return PortSpec(
        row["port_id"],
        row["direction"],
        row["service_node_id"],
        tuple(_place(p) for p in row["buffer_places"]),
        tuple((name, tick) for name, tick in row["service_ticks"]),
        tuple((start, end) for start, end in row["windows"]),
        frozenset(row["eligible_actor_ids"]),
    )


def profile_from_wire(row: Json) -> ExecutionProfile:
    actors = tuple(
        ActorSpec(
            a["actor_id"],
            a["home_node_id"],
            frozenset(a["skills"]),
            fraction(a["speed_m_s"]),
            fraction(a["max_gross_mass_kg"]),
        )
        for a in row["actors"]
    )
    return ExecutionProfile(
        row["profile_id"],
        row["layout_version"],
        row["graph_sha256"],
        tuple(SourceBinding(**s) for s in row["source_bindings"]),
        actors,
        tuple(_port(p) for p in row["ports"]),
        tuple(_place(p) for p in row["slots"]),
        tuple(_unit(hu) for hu in row["handling_units"]),
        tuple(InitialPlacement(**p) for p in row["initial_placements"]),
        tuple(TimedJob(**j) for j in row["jobs"]),
        HandlingTimes(**row["handling"]),
        row["provenance_note"],
    )


def _motion(row: Json | None) -> Motion | None:
    if row is None:
        return None
    route = row["route"]
    return Motion(
        CandidateRoute(
            route["graph_id"],
            tuple(route["node_ids"]),
            tuple(route["arc_ids"]),
            fraction(route["length_m"]),
            fraction(route["cost_m"]),
        ),
        row["start_tick"],
        row["end_tick"],
    )


def _worker(row: Json) -> WorkerView:
    return WorkerView(row["actor_id"], row["node_id"], _motion(row["motion"]), row["job_id"])


def _event(row: Json) -> ManualEvent:
    return ManualEvent(
        row["seq"],
        row["tick"],
        row["kind"],
        row["job_id"],
        row["hu_id"],
        row["actor_id"],
        row["stage"],
        row["location_id"],
        tuple(row["resource_ids"]),
        _motion(row["motion"]),
        None if row["owner"] is None else HUOwner(**row["owner"]),
        None if row["job"] is None else JobView(**row["job"]),
        None if row["worker"] is None else _worker(row["worker"]),
    )


def _snapshot(row: Json) -> ManualSnapshot:
    return ManualSnapshot(
        row["tick"],
        row["status"],
        tuple(JobView(**j) for j in row["jobs"]),
        tuple(_worker(w) for w in row["workers"]),
        tuple(HUOwner(**h) for h in row["owners"]),
        tuple(Lease(**lease) for lease in row["leases"]),
        tuple((sku, count) for sku, count in row["stock_units"]),
        tuple((sku, count) for sku, count in row["wip_units"]),
        tuple((sku, count) for sku, count in row["outside_units"]),
        tuple((sku, count) for sku, count in row["shipped_units"]),
    )


def outcome_from_wire(run: Json) -> ManualOutcome:
    return ManualOutcome(
        run["profile"]["profile_id"],
        tuple(_event(e) for e in run["events"]),
        _snapshot(run["at_horizon"]),
        _snapshot(run["at_end"]),
    )
