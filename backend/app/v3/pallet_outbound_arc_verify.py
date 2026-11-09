"""Recompute the pickup and first-arc evidence from raw pins on every public verification."""

from dataclasses import replace

from app.v3.pallet_outbound_arc_geometry import check_geometry
from app.v3.pallet_outbound_arc_models import METHOD, TRAVEL_STATUS, ArcCertificate, ArcPlan
from app.v3.pallet_outbound_arc_obstacles import check_obstacles
from app.v3.pallet_outbound_arc_plan import verify_arc_plan
from app.v3.pallet_outbound_pickup_geometry import source_scene
from app.v3.pallet_outbound_pickup_identity import identity, require_same
from app.v3.pallet_outbound_pickup_models import PickupCertificate, PickupPlan, PickupSource

LIMITATIONS = (
    "geometry_only_one_fixed_yaw_reverse_arc",
    "conditional_on_completed_source_bound_pickup_not_runtime_custody",
    "source_pickup_zero_lowering_clearance_unchanged",
    "PALLET_signed_physical_to_C08_relative_yaw_field_mapping_not_provided",
    "nonzero_declared_C08_relative_yaw_is_forbidden_no_pi_as_zero_waiver",
    "destination_stop_permission_unknown_no_following_turn_grant",
    "static_original_module_and_HU_boxes_only",
    "dynamic_occupancy_traffic_leases_and_actor_availability_not_proved",
    "quasistatic_contact_not_dynamic_retention_or_strength",
    "no_clock_runtime_ledger_paid_return_or_B2B_handoff",
)


def certify_arc(
    source: PickupSource,
    pickup: PickupPlan,
    pickup_certificate: PickupCertificate,
    plan: ArcPlan,
) -> ArcCertificate:
    verify_arc_plan(source, pickup, pickup_certificate, plan)
    scene = source_scene(source, pickup)
    geometry = check_geometry(scene, source, pickup, plan)
    obstacles = check_obstacles(source, pickup, plan, geometry.bounds)
    result = ArcCertificate(
        METHOD,
        source.source_hash,
        plan.plan_hash,
        scene.sha256,
        geometry.cover_checks,
        geometry.moving_solids,
        geometry.contacts,
        geometry.bounds,
        obstacles,
        geometry.endpoint_root_world,
        geometry.endpoint_axle_world,
        geometry.endpoint_hu_bottom_world,
        pickup_certificate.relative_hu_yaw_rad,
        None,
        TRAVEL_STATUS,
        LIMITATIONS,
        False,
        "",
    )
    return replace(result, certificate_hash=identity(result))


def verify_arc_certificate(
    source: PickupSource,
    pickup: PickupPlan,
    pickup_certificate: PickupCertificate,
    plan: ArcPlan,
    certificate: ArcCertificate,
) -> None:
    require_same(certificate, certify_arc(source, pickup, pickup_certificate, plan))
