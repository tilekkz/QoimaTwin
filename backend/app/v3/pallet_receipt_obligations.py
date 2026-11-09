"""Concrete absent fields for a new source-bound pickup proof and common execution policy."""

from app.v3.pallet_receipt_types import ProofObligation

PREFIX = "docs/v3/contract-proposals/"


def _staging_obligations() -> tuple[ProofObligation, ...]:
    return (
        ProofObligation(
            "STAGING_PICKUP_GEOMETRY_MISSING",
            "reserved_staging_pickup",
            (
                "per_position_support_id_and_mesh_hash",
                "support_world_pose_and_contact_height",
                "two_fork_channel_geometry",
                "actual_HU_initial_world_pose_and_orientation",
                "exclusive_local_action_space",
                "continuous_loaded_pickup_sweep_and_contact_proof",
            ),
            (PREFIX + "ports-v3.inbound.json", PREFIX + "vehicle-handling-v3.json"),
        ),
        ProofObligation(
            "STAGING_VEHICLE_CONNECTOR_MISSING",
            "port_to_staging_to_loaded_graph",
            (
                "staging_position_vehicle_pose_id",
                "directed_vehicle_connector_geometry",
                "fixed_pair_and_cargo_permissions",
                "loaded_and_empty_swept_clearance_evidence",
                "shared_traffic_resource_bindings",
            ),
            (PREFIX + "layout-links-v3.json", PREFIX + "ports-v3.inbound.json"),
        ),
    )


def receipt_obligations() -> tuple[ProofObligation, ...]:
    return (
        *_staging_obligations(),
        ProofObligation(
            "LOADED_ROUTE_ACTUAL_MODEL_PROOF_REQUIRED",
            "loaded_transit",
            (
                "actual_mesh_containment_in_accepted_travel_components",
                "retention_contact_authority_through_turns_and_reverse",
                "source_analytic_turns_not_root_polyline_interpolation",
            ),
            (PREFIX + "vehicle-handling-v3.json", PREFIX + "vehicle-graph-v3.json"),
        ),
        ProofObligation(
            "TARGET_PUTAWAY_PROOF_REQUIRED",
            "target_loaded_precondition",
            (
                "revalidated_local_putaway_suffix",
                "computed_attached_entry_connector_proof",
                "same_HU_vehicle_custody_and_empty_target",
                "actual_exclusive_action_space",
            ),
            ("backend/docs/adr/0070-v3-source-pallet-receipt-prerequisites.md",),
        ),
        ProofObligation(
            "SHARED_RECEIPT_PROCESS_POLICY_REQUIRED",
            "clock_and_credit",
            (
                "initial_F01_FL01_pose_and_paid_approach",
                "explicit_forward_reverse_speeds",
                "stop_steering_transition_times",
                "receiver_service_and_release_intervals",
                "no_double_count_of_30s_intake_and_mechanical_pickup",
                "credit_at_proved_completed_handoff_to_reserved_staging",
                "single_clock_worker_vehicle_traffic_and_target_reservations",
            ),
            (PREFIX + "ports-v3.inbound.json", PREFIX + "port-resource-policy-v3.json"),
        ),
    )
