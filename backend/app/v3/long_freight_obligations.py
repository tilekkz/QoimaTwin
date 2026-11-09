"""Finite actual-proof prerequisites; none can be cleared by a caller Boolean/hash."""

from app.v3.long_freight_models import LongFreightObligation


def _physical() -> tuple[LongFreightObligation, ...]:
    return (
        LongFreightObligation(
            "ACTUAL_PICKUP_CONTACT_REQUIRED",
            (
                "source_HU_signed_axes_and_support_pose",
                "actual_cargo_support_vehicle_meshes",
                "continuous_pickup_and_two_fork_contact",
                "no_yaw_normalization",
            ),
        ),
        LongFreightObligation(
            "CRADLE_LOCK_RETENTION_REQUIRED",
            (
                "actual_40kg_cradle_inventory_and_mount",
                "both_captive_pins_and_restraint",
                "actual_contact_lock_retention_and_strength_authority",
            ),
        ),
        LongFreightObligation(
            "ACTUAL_SETDOWN_CONTACT_REQUIRED",
            (
                "target_support_mesh_and_current_capacity",
                "continuous_setdown_and_release",
                "arm_pad_pocket_relief_and_stable_support",
            ),
        ),
        LongFreightObligation(
            "LOADED_ROUTE_GATE_SWEEP_REQUIRED",
            (
                "directed_source_target_port_and_return_routes",
                "actual_loaded_components",
                "signed_HU_vehicle_orientation",
                "gate_crossing_and_turn_sweeps",
                "stop_steering_reverse_obligations",
            ),
        ),
    )


def _process() -> tuple[LongFreightObligation, ...]:
    return (
        LongFreightObligation(
            "JOINT_ACTOR_VEHICLE_TRAFFIC_REQUIRED",
            (
                "actual_F02_FL02_initial_pose_and_seating",
                "driver_shipper_vehicle_availability",
                "exclusive_action_traffic_target_and_staging_leases",
                "shared_clock_custody",
            ),
        ),
        LongFreightObligation(
            "EXPLICIT_OPERATION_CLOCKS_REQUIRED",
            (
                "paid_approach_pickup_carry_place_return",
                "forward_reverse_lift_reach_stop_clocks",
                "service_scope_without_double_count",
                "per_operation_rounding_H_and_end",
            ),
        ),
        LongFreightObligation(
            "CUSTOMER_HANDOFF_AND_STAGING_REQUIRED",
            (
                "exact_customer_offer_and_single_original_consumption",
                "finite_staging_support",
                "actual_port_setdown_handoff_and_release",
                "unchanged_full_offered_stream",
            ),
        ),
    )


def obligations() -> tuple[LongFreightObligation, ...]:
    return (*_physical(), *_process())
