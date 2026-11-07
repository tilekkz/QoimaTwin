"""Fail closed on incomplete manual-execution profiles, before creating events."""

from fractions import Fraction

from app.v3.execution_types import (
    ACTOR_IDS,
    MANUAL_ARCHETYPES,
    BoundGraph,
    ExecutionProfile,
    HandlingUnit,
    PlaceSpec,
    PortSpec,
)


def _unique(values: tuple[str, ...]) -> None:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("execution identifiers must be nonempty strings")
    if len(values) != len(set(values)):
        raise ValueError("duplicate execution identifier")


def _tick(value: int, *, positive: bool = False) -> None:
    if type(value) is not int or value < int(positive):
        raise ValueError("execution times must be integer ticks with the declared sign")


def _positive(value: Fraction) -> None:
    if not isinstance(value, Fraction) or value <= 0:
        raise ValueError("execution dimensions, mass and speed must be positive fractions")


def _digest(value: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("source binding must use lowercase SHA256")


def fits(hu: HandlingUnit, place: PlaceSpec) -> bool:
    return (
        hu.archetype in place.allowed_archetypes
        and hu.gross_mass_kg <= place.max_payload_kg
        and all(
            a <= b for a, b in zip(hu.dimensions_xyz_m, place.usable_dimensions_xyz_m, strict=True)
        )
    )


def _places(profile: ExecutionProfile, nodes: set[str]) -> None:
    places = (*profile.slots, *(b for p in profile.ports for b in p.buffer_places))
    _unique(tuple(p.place_id for p in places))
    manual_places = {j.slot_id for j in profile.jobs} | {
        b.place_id for p in profile.ports for b in p.buffer_places
    }
    for place in places:
        if not place.allowed_archetypes or (
            place.place_id in manual_places and place.node_id not in nodes
        ):
            raise ValueError("place has missing graph anchor or cargo permissions")
        if len(place.usable_dimensions_xyz_m) != 3:
            raise ValueError("place dimensions need three axes")
        for value in (*place.usable_dimensions_xyz_m, place.max_payload_kg):
            _positive(value)


def _port(port: PortSpec, nodes: set[str]) -> None:
    if port.direction not in {"inbound", "outbound"} or port.service_node_id not in nodes:
        raise ValueError("port direction or service anchor is invalid")
    if not port.buffer_places or not port.windows or not port.eligible_actor_ids:
        raise ValueError("port needs finite buffer, windows and explicit actual actor IDs")
    if not port.eligible_actor_ids <= set(ACTOR_IDS):
        raise ValueError("port creates an unknown worker")
    _unique(tuple(archetype for archetype, _ in port.service_ticks))
    for _, duration in port.service_ticks:
        _tick(duration, positive=True)
    previous = -1
    for start, end in port.windows:
        _tick(start)
        _tick(end, positive=True)
        if start >= end or start < previous:
            raise ValueError("port windows must be ordered and nonoverlapping")
        previous = end


def _loads(profile: ExecutionProfile) -> None:
    _unique(tuple(h.hu_id for h in profile.handling_units))
    for hu in profile.handling_units:
        _unique((hu.sku_id,))
        _tick(hu.quantity, positive=True)
        if len(hu.dimensions_xyz_m) != 3:
            raise ValueError("HU dimensions need three axes")
        for value in (*hu.dimensions_xyz_m, hu.gross_mass_kg):
            _positive(value)


def _jobs(profile: ExecutionProfile) -> None:
    units = {hu.hu_id: hu for hu in profile.handling_units}
    ports = {p.port_id: p for p in profile.ports}
    slots = {s.place_id: s for s in profile.slots}
    _unique(tuple(j.job_id for j in profile.jobs))
    seen: set[tuple[str, str]] = set()
    for job in profile.jobs:
        _tick(job.arrival_tick)
        if job.hu_id not in units or job.port_id not in ports or job.slot_id not in slots:
            raise ValueError("job has unknown HU, port or storage slot")
        hu, port = units[job.hu_id], ports[job.port_id]
        if hu.archetype not in MANUAL_ARCHETYPES or hu.gross_mass_kg > 15:
            raise ValueError("manual jobs support SMALL/STANDARD complete HUs up to 15kg")
        if job.direction != port.direction or hu.archetype not in dict(port.service_ticks):
            raise ValueError("job and manual port capability do not match")
        if not fits(hu, slots[job.slot_id]) or not any(fits(hu, b) for b in port.buffer_places):
            raise ValueError("HU does not fit its slot or any finite buffer place")
        pair = job.hu_id, job.direction
        if pair in seen:
            raise ValueError("HU has duplicate same-direction jobs")
        seen.add(pair)


def _initial(profile: ExecutionProfile) -> None:
    units = {h.hu_id: h for h in profile.handling_units}
    slots = {s.place_id: s for s in profile.slots}
    _unique(tuple(p.hu_id for p in profile.initial_placements))
    _unique(tuple(p.slot_id for p in profile.initial_placements))
    initial = {p.hu_id for p in profile.initial_placements}
    inbound = {j.hu_id for j in profile.jobs if j.direction == "inbound"}
    if initial & inbound or initial | inbound != units.keys():
        raise ValueError("every HU needs exactly one initial or timed inbound origin")
    for placement in profile.initial_placements:
        if placement.slot_id not in slots or not fits(
            units[placement.hu_id], slots[placement.slot_id]
        ):
            raise ValueError("initial HU placement is missing or incompatible")


def validate_profile(profile: ExecutionProfile, graph: BoundGraph) -> None:
    _unique((profile.profile_id,))
    _unique((profile.layout_version,))
    if (profile.layout_version, profile.graph_sha256) != (graph.layout_version, graph.sha256):
        raise ValueError("execution graph source binding mismatch")
    if graph.graph.graph_id != "walk":
        raise ValueError("manual execution requires the directed walk graph")
    _digest(profile.graph_sha256)
    if not profile.source_bindings or not profile.provenance_note.strip():
        raise ValueError("execution needs explicit source bindings and assumption provenance")
    _unique(tuple(s.path for s in profile.source_bindings))
    for source in profile.source_bindings:
        _digest(source.sha256)
    _unique(tuple(a.actor_id for a in profile.actors))
    if {a.actor_id for a in profile.actors} != set(ACTOR_IDS):
        raise ValueError("execution must preserve all 24 actual actor IDs")
    nodes = set(graph.graph.node_ids)
    for actor in profile.actors:
        if actor.home_node_id not in nodes or not actor.skills <= {"receive", "ship"}:
            raise ValueError("actor has missing home or unsupported manual skill")
        _positive(actor.speed_m_s)
        _positive(actor.max_gross_mass_kg)
    _unique(tuple(p.port_id for p in profile.ports))
    for port in profile.ports:
        _port(port, nodes)
    _tick(profile.handling.pickup_ticks, positive=True)
    _tick(profile.handling.place_ticks, positive=True)
    _places(profile, nodes)
    _loads(profile)
    _jobs(profile)
    _initial(profile)
