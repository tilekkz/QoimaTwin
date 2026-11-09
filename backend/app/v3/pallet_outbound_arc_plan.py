"""A closed first-arc plan bound to fully recomputed source pickup authority."""

from dataclasses import replace
from fractions import Fraction as F

import numpy as np

from app.v3.pallet_outbound_arc_models import METHOD, TRAVEL_STATUS, ArcPlan
from app.v3.pallet_outbound_arc_source import arc_facts
from app.v3.pallet_outbound_pickup_frames import vector
from app.v3.pallet_outbound_pickup_identity import identity, require_same
from app.v3.pallet_outbound_pickup_models import PickupCertificate, PickupPlan, PickupSource
from app.v3.pallet_outbound_pickup_verify import verify_pickup_certificate


def compile_arc_plan(
    source: PickupSource,
    pickup: PickupPlan,
    certificate: PickupCertificate,
) -> ArcPlan:
    verify_pickup_certificate(source, pickup, certificate)
    facts = arc_facts(source)
    arc, end = facts["arc"], facts["end_node"]
    geometry = arc["geometry"]
    length = F(str(arc["length_m"]))
    start = pickup.segments[-1].end
    result = ArcPlan(
        METHOD,
        source.source_hash,
        pickup.plan_hash,
        certificate.certificate_hash,
        pickup.hu_id,
        pickup.unit_ids,
        pickup.actor_id,
        pickup.vehicle_id,
        str(arc["arc_id"]),
        str(arc["from_node_id"]),
        str(arc["to_node_id"]),
        start,
        replace(start, root_z=start.root_z - length),
        certificate.endpoint_root_world,
        vector(np.array(end["world_pos"])),
        certificate.endpoint_axle_world,
        (float(geometry["front_axle_end_xz_m"][0]), 0.0, float(geometry["front_axle_end_xz_m"][1])),
        pickup.source_yaw_rad,
        -1,
        length,
        F(str(arc["clearance_padding_m"])),
        F(str(facts["top_padding"])),
        F(str(arc["clear_height_m"])),
        None,
        TRAVEL_STATUS,
        False,
        "",
    )
    return replace(result, plan_hash=identity(result))


def verify_arc_plan(
    source: PickupSource,
    pickup: PickupPlan,
    certificate: PickupCertificate,
    plan: ArcPlan,
) -> None:
    require_same(plan, compile_arc_plan(source, pickup, certificate))
