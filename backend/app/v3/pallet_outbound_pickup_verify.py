"""Recompute source-bound geometry; caller assertions or rehashes confer no authority."""

from dataclasses import replace
from hashlib import sha256

from app.v3.mesh_proof_source import ACTION_PATH, MESH_PATH
from app.v3.pallet_outbound_pickup_endpoint import check_endpoint
from app.v3.pallet_outbound_pickup_geometry import (
    action_bounds,
    check_contacts,
    check_sweeps,
    mesh_segments,
    source_scene,
)
from app.v3.pallet_outbound_pickup_identity import identity, require_same
from app.v3.pallet_outbound_pickup_models import PickupCertificate, PickupPlan, PickupSource
from app.v3.pallet_outbound_pickup_obstacles import check_obstacles
from app.v3.pallet_outbound_pickup_plan import METHOD, verify_pickup_plan
from app.v3.pallet_outbound_pickup_source import raw_document

LIMITATIONS = (
    "geometry_only",
    "proposed_action_not_measured",
    "zero_fore_aft_gap_during_lowering",
    "positive_handling_clearance_not_proved",
    "seated_F02_not_proved",
    "loaded_route_not_proved",
    "traffic_and_dynamic_occupancy_not_proved",
    "timing_and_paid_accounting_not_proved",
    "ledger_custody_not_implemented",
    "B2B_support_and_handoff_missing",
    "quasi_static_declared_CoG_only",
    "retention_rating_strength_not_proved",
    "relative_HU_yaw_pi_not_a_semantic_travel_grant",
    "C08_zero_relative_yaw_rule_has_no_grant_for_this_geometric_binding",
    "nominal_job_load_frame_semantics_not_resolved",
)


def certify_pickup(source: PickupSource, plan: PickupPlan) -> PickupCertificate:
    verify_pickup_plan(source, plan)
    scene = source_scene(source, plan)
    segments = mesh_segments(plan)
    checks = check_sweeps(scene, segments)
    contacts = check_contacts(scene, segments)
    action = action_bounds(scene, plan, segments)
    obstacles = check_obstacles(source, plan, action)
    endpoint, hu, root, axle, arc = check_endpoint(scene, source, plan, segments[-1].end)
    hashes = [
        sha256(raw_document(source, "v3-mesh-proof-proposal", path)).hexdigest()
        for path in (MESH_PATH, ACTION_PATH)
    ]
    result = PickupCertificate(
        METHOD,
        source.source_hash,
        plan.plan_hash,
        hashes[0],
        hashes[1],
        checks,
        contacts,
        action,
        endpoint,
        hu,
        obstacles,
        root,
        axle,
        arc,
        plan.hu_yaw_rad - plan.source_yaw_rad,
        "not_admitted_pending_C08_relative_yaw_frame_binding",
        LIMITATIONS,
        False,
        False,
        "",
    )
    return replace(result, certificate_hash=identity(result))


def verify_pickup_certificate(
    source: PickupSource, plan: PickupPlan, certificate: PickupCertificate
) -> None:
    require_same(certificate, certify_pickup(source, plan))
