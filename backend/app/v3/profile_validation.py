"""Admission of timed jobs only; source stock remains complete and unchanged."""

from fractions import Fraction

from app.v3.execution_types import ACTOR_IDS, ExecutionProfile, HandlingUnit, PlaceSpec
from app.v3.input_models import V3Bundle
from app.v3.materialize import number
from app.v3.profile_build import document
from app.v3.profile_models import ManualProposal
from app.v3.runtime_graph import DirectedGraph, RouteRequirements


def validate_jobs(
    bundle: V3Bundle, proposal: ManualProposal, profile: ExecutionProfile, graph: DirectedGraph
) -> None:
    if {a.actor_id for a in profile.actors} != set(ACTOR_IDS) or len(profile.actors) != 24:
        raise ValueError("preserve all 24 explicit actor IDs")
    source_slots = {r["slot_id"]: r for r in document(bundle, "storage-slots-v3.json")["slots"]}
    loads = {h.hu_id: h for h in profile.handling_units}
    places = {s.place_id: s for s in profile.slots}
    ports = {p.port_id: p for p in profile.ports}
    occupied = {p.slot_id: p.hu_id for p in profile.initial_placements}
    targets: set[str] = set()
    for job in profile.jobs:
        if job.hu_id not in loads or job.slot_id not in source_slots or job.port_id not in ports:
            raise ValueError("job has unknown HU, slot or port")
        hu, slot, port = loads[job.hu_id], source_slots[job.slot_id], ports[job.port_id]
        if hu.archetype not in {"SMALL_CARTON", "STANDARD_CARTON"} or hu.gross_mass_kg > 15:
            raise ValueError("unsupported manual job cargo")
        if not slot["manual_pick_allowed"] or slot["reserve_only"] or slot["retrieval_blocked"]:
            raise ValueError("unsupported reserve or nonmanual slot")
        if job.direction != port.direction or hu.archetype not in dict(port.service_ticks):
            raise ValueError("unsupported direction or port cargo")
        if job.direction == "inbound":
            if job.slot_id in occupied or job.slot_id in targets or job.hu_id in occupied.values():
                raise ValueError("receipt needs a compatible initially free unique address")
            targets.add(job.slot_id)
        elif job.direction != "outbound" or occupied.get(job.slot_id) != job.hu_id:
            raise ValueError("outbound must use its exact source placement")
        _fit(hu.dimensions_xyz_m, hu.gross_mass_kg, hu.archetype, places[job.slot_id])
        for buffer in port.buffer_places:
            _fit(hu.dimensions_xyz_m, hu.gross_mass_kg, hu.archetype, buffer)
        _routes(proposal, profile, graph, job.port_id, places[job.slot_id].node_id, hu)
    _module_payload(bundle, profile)


def _fit(
    dims: tuple[Fraction, Fraction, Fraction], mass: Fraction, archetype: str, place: PlaceSpec
) -> None:
    if archetype not in place.allowed_archetypes:
        raise ValueError("cargo not permitted in place")
    if mass > place.max_payload_kg or any(
        a > b for a, b in zip(dims, place.usable_dimensions_xyz_m, strict=True)
    ):
        raise ValueError("cargo exceeds exact cleared envelope or payload")


def _routes(
    proposal: ManualProposal,
    profile: ExecutionProfile,
    graph: DirectedGraph,
    port_id: str,
    slot_node: str,
    hu: HandlingUnit,
) -> None:
    width, height = number(proposal.carry_width_m), number(proposal.carry_height_m)
    if width < max(hu.dimensions_xyz_m[0], hu.dimensions_xyz_m[2]) + Fraction("0.1"):
        raise ValueError("declared carry envelope lacks 0.05m per-side cargo clearance")
    if height < max(Fraction("1.8"), hu.dimensions_xyz_m[1]):
        raise ValueError("declared carry envelope is too low")
    required = RouteRequirements(
        mode="pedestrian", min_clear_width_m=width, min_clear_height_m=height
    )
    port = next(p for p in profile.ports if p.port_id == port_id)
    actors = [a for a in profile.actors if a.actor_id in port.eligible_actor_ids]
    if not actors or any(a.max_gross_mass_kg < hu.gross_mass_kg for a in actors):
        raise ValueError("eligible actor lacks declared mass capacity")
    anchors = {
        slot_node,
        port.service_node_id,
        *(b.node_id for b in port.buffer_places),
        *(a.home_node_id for a in actors),
    }
    for start in anchors:
        for end in anchors:
            if graph.shortest_path(start, end, required) is None:
                raise ValueError("missing directed pedestrian route with carry clearance")
            # Engine uses mode-only Dijkstra: its actual chosen route must also fit.
            route = graph.shortest_path(start, end, RouteRequirements(mode="pedestrian"))
            if route != graph.shortest_path(start, end, required):
                raise ValueError("engine mode-only route differs from cleared route")


def _module_payload(bundle: V3Bundle, profile: ExecutionProfile) -> None:
    rows = document(bundle, "storage-slots-v3.json")
    slots = {s.slot_id: s.module_id for s in bundle.slots}
    mass = {h.hu_id: h.gross_mass_kg for h in profile.handling_units}
    totals: dict[str, Fraction] = {}
    additions = [(p.hu_id, p.slot_id) for p in profile.initial_placements]
    additions += [(j.hu_id, j.slot_id) for j in profile.jobs if j.direction == "inbound"]
    for hu_id, slot_id in additions:
        module = slots[slot_id]
        totals[module] = totals.get(module, Fraction(0)) + mass[hu_id]
    for module in rows["modules"]:
        if totals.get(module["module_id"], Fraction(0)) > Fraction(
            str(module["max_module_payload_kg"])
        ):
            raise ValueError("conservative initial plus receipts exceeds module payload")
