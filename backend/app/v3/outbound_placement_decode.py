"""Decode explicit choices only; derived decisions must be recomputed from source."""

from fractions import Fraction

from app.v3.outbound_placement_models import (
    PlacementActor,
    PlacementCandidate,
    PlacementChoices,
    PlacementCustomer,
    PlacementReceiptTarget,
)
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.staff_registry_values import array, object_fields, text


def _fraction(value: object) -> Fraction:
    values = array(value)
    require(
        len(values) == 2 and all(type(v) is int for v in values) and values[1] > 0,
        "Exact rational pair required",
    )
    result = Fraction(values[0], values[1])
    require([result.numerator, result.denominator] == values, "Canonical rational pair required")
    return result


def _actor(value: object) -> PlacementActor:
    row = object_fields(value, "actor_id home_node_id speed_m_s max_gross_kg")
    return PlacementActor(
        text(row["actor_id"]),
        text(row["home_node_id"]),
        _fraction(row["speed_m_s"]),
        _fraction(row["max_gross_kg"]),
    )


def _customer(value: object) -> PlacementCustomer | None:
    if value is None:
        return None
    row = object_fields(
        value, "offer_id port_id buffer_choice pickup_ticks place_ticks service_ticks"
    )
    return PlacementCustomer(
        text(row["offer_id"]),
        text(row["port_id"]),
        text(row["buffer_choice"]).encode("utf-8"),
        row["pickup_ticks"],
        row["place_ticks"],
        row["service_ticks"],
    )


def _candidate(value: object) -> PlacementCandidate:
    row = object_fields(
        value, "hu_id from_slot_id to_slot_id actor take_ticks place_ticks customer"
    )
    return PlacementCandidate(
        text(row["hu_id"]),
        text(row["from_slot_id"]),
        text(row["to_slot_id"]),
        _actor(row["actor"]),
        row["take_ticks"],
        row["place_ticks"],
        _customer(row["customer"]),
    )


def _receipt(value: object) -> PlacementReceiptTarget:
    row = object_fields(value, "receipt_job_id hu_id slot_id")
    return PlacementReceiptTarget(*(text(row[k]) for k in ("receipt_job_id", "hu_id", "slot_id")))


def decode_choices(value: object) -> PlacementChoices:
    row = object_fields(
        value,
        "policy_id candidates permitted_actor_ids route_policy min_width_m "
        "min_height_m path_clearance_m receipt_targets",
    )
    return PlacementChoices(
        text(row["policy_id"]),
        tuple(_candidate(v) for v in array(row["candidates"])),
        tuple(text(v) for v in array(row["permitted_actor_ids"])),
        text(row["route_policy"]),
        _fraction(row["min_width_m"]),
        _fraction(row["min_height_m"]),
        _fraction(row["path_clearance_m"]),
        tuple(_receipt(v) for v in array(row["receipt_targets"])),
    )
