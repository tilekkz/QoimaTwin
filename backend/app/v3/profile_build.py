"""Source projections for the bounded synthetic manual compiler."""

from fractions import Fraction
from typing import Any

from app.v3.execution_types import ActorSpec, HandlingUnit, PlaceSpec, PortSpec
from app.v3.input_models import V3Bundle
from app.v3.materialize import calendar_tick, number
from app.v3.profile_models import ManualProposal

PREFIX = "docs/v3/contract-proposals/"


def document(bundle: V3Bundle, name: str) -> Any:
    return bundle.documents[PREFIX + name].decode()


def dimensions(values: Any) -> tuple[Fraction, Fraction, Fraction]:
    x, y, z = values
    return Fraction(str(x)), Fraction(str(y)), Fraction(str(z))


def actors(proposal: ManualProposal, nodes: set[str]) -> tuple[ActorSpec, ...]:
    result = []
    for actor in proposal.actors:
        if actor.home_node_id not in nodes or not set(actor.skills) <= {"receive", "ship"}:
            raise ValueError("unknown actor home or skill")
        if number(actor.speed_m_s) != Fraction("1.3"):
            raise ValueError("V3 pedestrian speed must be 1.3m/s")
        result.append(
            ActorSpec(
                actor.actor_id,
                actor.home_node_id,
                frozenset(actor.skills),
                number(actor.speed_m_s),
                number(actor.max_gross_mass_kg),
            )
        )
    return tuple(result)


def storage(bundle: V3Bundle, nodes: set[str]) -> tuple[PlaceSpec, ...]:
    result = []
    for row in document(bundle, "storage-slots-v3.json")["slots"]:
        # Inactive heavy stock has a real typed pedestrian observer anchor;
        # this is never permission to handle cargo at that address.
        anchor = row["access"]["worker_node_id"]
        refs = row["typed_access_references"]
        if anchor not in nodes or not any(r["id"] == anchor and r["graph"] == "walk" for r in refs):
            raise ValueError("slot lacks bound typed pedestrian reference")
        clearance = Fraction(str(row["clearance_each_side_m"]))
        usable = tuple(v - 2 * clearance for v in dimensions(row["usable_dimensions_xyz_m"]))
        result.append(
            PlaceSpec(
                row["slot_id"],
                anchor,
                dimensions(usable),
                Fraction(str(row["max_payload_kg"])),
                frozenset(row["allowed_cargo_archetype_ids"]),
            )
        )
    return tuple(result)


def loads(bundle: V3Bundle, proposal: ManualProposal) -> tuple[HandlingUnit, ...]:
    classes = {a.archetype_id: a for a in bundle.cargo_archetypes}
    result = [
        HandlingUnit(
            h.handling_unit_id,
            h.sku_id,
            h.quantity_units,
            h.archetype_id,
            Fraction(str(h.gross_mass_kg)),
            dimensions(classes[h.archetype_id].dimensions_xyz_m),
        )
        for h in bundle.handling_units
    ]
    originals = {h.hu_id: h for h in result}
    for job in proposal.jobs:
        if job.receipt_template_hu_id is None:
            continue
        if job.direction != "inbound" or job.hu_id in originals:
            raise ValueError("receipt needs a unique new HU identity")
        if job.receipt_template_hu_id not in originals:
            raise ValueError("unknown source HU template")
        h = originals[job.receipt_template_hu_id]
        result.append(
            HandlingUnit(
                job.hu_id, h.sku_id, h.quantity, h.archetype, h.gross_mass_kg, h.dimensions_xyz_m
            )
        )
    if len({h.hu_id for h in result}) != len(result):
        raise ValueError("duplicate HU identity")
    return tuple(result)


def ports(
    bundle: V3Bundle, proposal: ManualProposal, buffers: tuple[tuple[str, PlaceSpec], ...]
) -> tuple[PortSpec, ...]:
    result = []
    source_roles = _source_actor_pools(bundle, proposal)
    for port_id in sorted({port_id for port_id, _ in buffers}):
        matches = [p for p in bundle.ports if p.port_id == port_id]
        if len(matches) != 1:
            raise ValueError("unknown manual port")
        port = matches[0]
        places = tuple(place for pid, place in buffers if pid == port_id)
        if len(places) > port.buffer_capacity:
            raise ValueError("synthetic buffers exceed source ceiling")
        skill = "receive" if port.direction == "inbound" else "ship"
        eligible = source_roles[skill]
        if not eligible:
            raise ValueError("manual port needs explicit eligible operators")
        result.append(
            PortSpec(
                port_id,
                port.direction,
                port.service_node_id,
                places,
                tuple(
                    (a, calendar_tick(str(s)))
                    for a, s in port.seconds_by_archetype
                    if a in {"SMALL_CARTON", "STANDARD_CARTON"}
                ),
                tuple((calendar_tick(str(a)), calendar_tick(str(b))) for a, b in port.open_windows),
                eligible,
            )
        )
    return tuple(result)


def _source_actor_pools(bundle: V3Bundle, proposal: ManualProposal) -> dict[str, frozenset[str]]:
    policy = document(bundle, "port-resource-policy-v3.json")
    pools = {row["pool_id"]: frozenset(row["actor_ids"]) for row in policy["pools"]}
    result: dict[str, frozenset[str]] = {}
    for skill, pool_id in (("receive", "RECEIVERS_SHARED"), ("ship", "SHIPPERS_SHARED")):
        if pool_id not in pools:
            raise ValueError("source port resource pool is missing")
        declared = frozenset(a.actor_id for a in proposal.actors if skill in a.skills)
        if not declared <= pools[pool_id]:
            raise ValueError("synthetic role allocation exceeds the fixed source port pool")
        result[skill] = declared & pools[pool_id]
    return result
