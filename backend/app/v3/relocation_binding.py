"""Separately versioned N1 inputs bind exact canonical common inputs and source plans."""

from fractions import Fraction
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.coordinator_profile import load_coordinator_inputs
from app.v3.flow_profile_wire import record
from app.v3.inputs import load_v3_bundle
from app.v3.relocation_admission import source_places
from app.v3.relocation_models import (
    RELOCATION_VERSION,
    BoundRelocation,
    RelocationChoices,
    RelocationJob,
    RelocationProfile,
)
from app.v3.relocation_plan import plan_relocations, validate_choices
from app.v3.runtime_time import DURATION_ROUNDING
from app.v3.settings import default_inputs
from app.v3.staff_registry_values import array, object_fields, text
from app.v3.stock_validation import require

INPUT_SCOPE = "source_bound_manual_relocation_plan_only"


def bind_relocation_source(common_inputs: bytes, choices: RelocationChoices) -> BoundRelocation:
    validate_choices(choices)
    require(type(common_inputs) is bytes, "Exact immutable common inputs required")
    common = load_coordinator_inputs(common_inputs)
    require(
        all(j.arrival_tick < common.horizon_tick for j in choices.jobs),
        "Relocation arrival must precede H",
    )
    bundle = load_v3_bundle(default_inputs())
    places = source_places(bundle, common.profile, choices.jobs)
    profile = RelocationProfile(
        choices.profile_id,
        choices.provenance,
        common.profile,
        choices.jobs,
        choices.permitted_actor_ids,
        places,
        choices.route_policy,
        choices.min_width_m,
        choices.min_height_m,
    )
    plans = plan_relocations(profile)
    frozen = canonical_bytes(
        {
            "schema_version": RELOCATION_VERSION,
            "scope": INPUT_SCOPE,
            "common_input_hash": common.input_hash,
            "common_inputs": parse_json(common_inputs),
            "choices": record(choices),
            "places": record(places),
            "plans": record(plans),
            "route_policy": choices.route_policy,
            "rounding": DURATION_ROUNDING,
            "horizon_tick": common.horizon_tick,
            "end_tick": common.end_tick,
        }
    )
    return BoundRelocation(
        profile, plans, choices, common_inputs, frozen, sha256(frozen).hexdigest()
    )


def load_relocation_inputs(raw: bytes) -> BoundRelocation:
    require(type(raw) is bytes, "Exact immutable relocation inputs required")
    value = object_fields(
        parse_json(raw),
        "schema_version scope common_input_hash common_inputs choices places plans "
        "route_policy rounding horizon_tick end_tick",
    )
    require(value["schema_version"] == RELOCATION_VERSION, "Relocation input version")
    require(value["scope"] == INPUT_SCOPE, "Relocation input scope")
    choice_fields = object_fields(
        value["choices"],
        "profile_id provenance jobs permitted_actor_ids route_policy min_width_m min_height_m",
    )
    choices = decode_relocation_choices({"schema_version": RELOCATION_VERSION, **choice_fields})
    expected = bind_relocation_source(canonical_bytes(value["common_inputs"]), choices)
    require(expected.frozen_bytes == raw, "Relocation frozen source/plan binding mismatch")
    return expected


def validate_bound_relocation(bound: BoundRelocation) -> None:
    require(type(bound) is BoundRelocation, "Exact bound relocation input required")
    expected = load_relocation_inputs(bound.frozen_bytes)
    require_same_authority(bound, expected)


def decode_relocation_choices(value: object) -> RelocationChoices:
    row = object_fields(
        value,
        "schema_version profile_id provenance jobs permitted_actor_ids "
        "route_policy min_width_m min_height_m",
    )
    require(row["schema_version"] == RELOCATION_VERSION, "Relocation choice version")
    choices = RelocationChoices(
        text(row["profile_id"]),
        text(row["provenance"]),
        tuple(_job(j) for j in array(row["jobs"])),
        tuple(text(a) for a in array(row["permitted_actor_ids"])),
        text(row["route_policy"]),
        _fraction(row["min_width_m"]),
        _fraction(row["min_height_m"]),
    )
    validate_choices(choices)
    return choices


def _fraction(value: Any) -> Fraction:
    row = object_fields(value, "numerator denominator")
    require(
        type(row["numerator"]) is int and type(row["denominator"]) is int,
        "Exact integer rational components required",
    )
    require(row["denominator"] > 0, "Positive rational denominator required")
    return Fraction(row["numerator"], row["denominator"])


def _job(value: object) -> RelocationJob:
    row = object_fields(
        value, "job_id arrival_tick hu_id from_slot_id to_slot_id actor_id take_ticks place_ticks"
    )
    return RelocationJob(**row)
