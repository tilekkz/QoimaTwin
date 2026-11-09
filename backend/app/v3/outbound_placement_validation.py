"""Exact immutable choices; declarations never become measured resource availability."""

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.outbound_placement_models import (
    PlacementActor,
    PlacementCandidate,
    PlacementChoices,
    PlacementCustomer,
    PlacementReceiptTarget,
)
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.profile_models import BufferChoice
from app.v3.staff_registry_values import text, tick, typed_tuple
from app.v3.stock_validation import exact
from app.v3.whole_profile_geometry import ROUTE_POLICY


def validate_actor(actor: PlacementActor) -> None:
    require(type(actor) is PlacementActor, "Exact PlacementActor required")
    text(actor.actor_id)
    text(actor.home_node_id)
    exact(actor.speed_m_s, positive=True)
    exact(actor.max_gross_kg, positive=True)


def positive_tick(value: int) -> None:
    require(tick(value) > 0, "Positive explicit operation ticks required")


def buffer_choice(customer: PlacementCustomer) -> BufferChoice:
    require(type(customer.buffer_choice) is bytes, "Exact immutable buffer choice bytes required")
    value = parse_json(customer.buffer_choice)
    require(canonical_bytes(value) == customer.buffer_choice, "Canonical buffer choice required")
    return BufferChoice.model_validate(value)


def validate_candidate(candidate: PlacementCandidate) -> None:
    require(type(candidate) is PlacementCandidate, "Exact PlacementCandidate required")
    for value in (candidate.hu_id, candidate.from_slot_id, candidate.to_slot_id):
        text(value)
    validate_actor(candidate.actor)
    positive_tick(candidate.take_ticks)
    positive_tick(candidate.place_ticks)
    if candidate.customer is not None:
        customer = candidate.customer
        require(type(customer) is PlacementCustomer, "Exact PlacementCustomer required")
        text(customer.offer_id)
        text(customer.port_id)
        for duration in (customer.pickup_ticks, customer.place_ticks, customer.service_ticks):
            positive_tick(duration)
        buffer_choice(customer)


def validate_choices(choices: PlacementChoices) -> None:
    require(type(choices) is PlacementChoices, "Exact PlacementChoices required")
    text(choices.policy_id)
    typed_tuple(choices.candidates, PlacementCandidate)
    require(len(choices.candidates) <= 1, "Only zero or one explicit candidate")
    typed_tuple(choices.permitted_actor_ids, str)
    for actor in choices.permitted_actor_ids:
        require(text(actor) in {"S01", "S02"}, "Only existing S01/S02 permission")
    require(
        len(set(choices.permitted_actor_ids)) == len(choices.permitted_actor_ids),
        "Duplicate actor permission",
    )
    require(
        type(choices.route_policy) is str and choices.route_policy == ROUTE_POLICY,
        "Explicit absent-only manual route policy required",
    )
    exact(choices.min_width_m, positive=True)
    exact(choices.min_height_m, positive=True)
    exact(choices.path_clearance_m)
    typed_tuple(choices.receipt_targets, PlacementReceiptTarget)
    for target in choices.receipt_targets:
        for value in (target.receipt_job_id, target.hu_id, target.slot_id):
            text(value)
    for candidate in choices.candidates:
        validate_candidate(candidate)
