"""Fresh F02/FL02 conditional fit; retained metadata never grants source authority."""

from dataclasses import replace

import numpy as np

from app.v3.pallet_operator_fit_geometry import (
    check_anchors,
    check_body_clearance,
    check_contacts,
    check_portal,
    check_roof,
    vehicle_parts,
)
from app.v3.pallet_operator_fit_models import (
    OperatorFitCertificate,
    OperatorFitChecks,
    OperatorFitSource,
)
from app.v3.pallet_operator_fit_motion import check_motion
from app.v3.pallet_operator_fit_pose import fit_scenes
from app.v3.pallet_operator_fit_source import (
    WORKER_SHA256,
    forklift_spec,
    verify_operator_fit_source,
    verify_outbound_pair,
)
from app.v3.pallet_outbound_pickup_frames import ry, vector
from app.v3.pallet_outbound_pickup_identity import identity, require_same
from app.v3.pallet_outbound_pickup_models import PickupPlan
from app.v3.pallet_outbound_pickup_plan import verify_pickup_plan

METHOD = "qoima-F02-FL02-conditional-operator-fit-v1"
LIMITATIONS = (
    "conditional_source_seated_pose_not_observed_presence",
    "seated_portal_projection_only_no_boarding_path",
    "six_root_relative_affine_carriage_reach_fork_intervals_and_radial_wheel_envelopes",
    "no_cargo_body_or_warehouse_clearance_certificate",
    "no_actual_initial_state_availability_or_resource_lease",
    "no_travel_steering_traffic_or_dynamic_occupancy_admission",
    "no_body_CoG_dynamic_restraint_strength_or_ergonomic_rating",
    "no_timing_paid_accounting_stock_custody_or_B2B_handoff",
    "pickup_zero_gap_and_C08_orientation_limits_unchanged",
)


def certify_operator_fit(source: OperatorFitSource, plan: PickupPlan) -> OperatorFitCertificate:
    verify_operator_fit_source(source)
    verify_pickup_plan(source.pickup, plan)
    pair_id = verify_outbound_pair(source, plan.actor_id, plan.vehicle_id)
    person, vehicle = fit_scenes(source)
    spec = forklift_spec(source)
    count = check_body_clearance(person, vehicle_parts(vehicle))
    intervals, wheels = check_motion(vehicle, person, plan)
    checks = OperatorFitChecks(
        count,
        len(vehicle_parts(vehicle)),
        sum(len(p.triangles) for p in person.parts),
        check_anchors(person, vehicle, spec),
        check_contacts(person, vehicle, spec),
        check_roof(person, vehicle, spec),
        check_portal(person, spec),
        intervals,
        wheels,
    )
    root = np.array(plan.source_root_world) + ry(plan.source_yaw_rad) @ np.array(
        spec["driver"]["worker_root_translation"]
    )
    result = OperatorFitCertificate(
        METHOD,
        source.source_hash,
        plan.plan_hash,
        plan.actor_id,
        plan.vehicle_id,
        pair_id,
        WORKER_SHA256,
        vehicle.sha256,
        checks,
        vector(root),
        LIMITATIONS,
        False,
        False,
        False,
        False,
        "",
    )
    return replace(result, certificate_hash=identity(result))


def verify_operator_fit_certificate(
    source: OperatorFitSource,
    plan: PickupPlan,
    retained: OperatorFitCertificate,
) -> OperatorFitCertificate:
    fresh = certify_operator_fit(source, plan)
    require_same(retained, fresh)
    return fresh
