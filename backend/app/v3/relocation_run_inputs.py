"""Separate analytical and source-bound N1 inputs; neither path executes a scheduler."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_native_decode import decode, encode
from app.v3.coordinator_run_inputs import HandCoordinatorInputs
from app.v3.coordinator_run_inputs import freeze_hand_inputs as freeze_coordinator
from app.v3.coordinator_run_inputs import load_run_inputs as load_coordinator
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.relocation_binding import load_relocation_inputs
from app.v3.relocation_models import (
    RELOCATION_VERSION,
    BoundRelocation,
    RelocationChoices,
    RelocationPlace,
    RelocationProfile,
)
from app.v3.relocation_plan import plan_relocations
from app.v3.runtime_time import DURATION_ROUNDING

HAND_VERSION = "qoima-relocation-hand-inputs-0.1.0"


@dataclass(frozen=True, slots=True)
class HandRelocationInputs(BoundRelocation):
    """Explicit analytical inputs cannot impersonate source-bound admission."""


def freeze_hand_inputs(
    profile: RelocationProfile, conveyor: ConveyorSource, horizon_tick: int, end_tick: int
) -> HandRelocationInputs:
    if type(profile) is not RelocationProfile:
        raise ValueError("Exact analytical relocation profile required")
    require_same_authority(profile, decode(RelocationProfile, encode(profile)))
    common = freeze_coordinator(profile.coordinator, conveyor, horizon_tick, end_tick)
    if any(job.arrival_tick >= horizon_tick for job in profile.jobs):
        raise ValueError("Relocation arrival must precede the publication horizon")
    plans = plan_relocations(profile)
    choices = RelocationChoices(
        profile.profile_id,
        profile.provenance,
        profile.jobs,
        profile.permitted_actor_ids,
        profile.route_policy,
        profile.min_width_m,
        profile.min_height_m,
    )
    raw = canonical_bytes(
        {
            "schema_version": HAND_VERSION,
            "engine_version": RELOCATION_VERSION,
            "scope": "analytical_fixture",
            "common_inputs": parse_json(common.frozen_bytes),
            "choices": encode(choices),
            "places": encode(profile.places),
            "plans": encode(plans),
            "rounding": DURATION_ROUNDING,
        }
    )
    return HandRelocationInputs(
        profile, plans, choices, common.frozen_bytes, raw, sha256(raw).hexdigest()
    )


def _load_hand(raw: bytes, value: dict[str, Any]) -> HandRelocationInputs:
    keys = {
        "schema_version",
        "engine_version",
        "scope",
        "common_inputs",
        "choices",
        "places",
        "plans",
        "rounding",
    }
    if value.keys() != keys or value["scope"] != "analytical_fixture":
        raise ValueError("Analytical relocation fields or scope differ")
    common = load_coordinator(canonical_bytes(value["common_inputs"]))
    if type(common) is not HandCoordinatorInputs:
        raise ValueError("Analytical relocation cannot impersonate source-bound inputs")
    choices = decode(RelocationChoices, value["choices"])
    places = decode(tuple[RelocationPlace, ...], value["places"])
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
    _, conveyor, _ = _pinned_reference()
    result = freeze_hand_inputs(profile, conveyor, common.horizon_tick, common.end_tick)
    if result.frozen_bytes != raw:
        raise ValueError("Analytical relocation frozen plans or policy differ")
    return result


def load_run_inputs(raw: bytes) -> BoundRelocation:
    if type(raw) is not bytes:
        raise ValueError("Relocation inputs require exact immutable bytes")
    value = parse_json(raw)
    if type(value) is not dict or canonical_bytes(value) != raw:
        raise ValueError("Relocation inputs require canonical object bytes")
    if value.get("schema_version") == HAND_VERSION:
        return _load_hand(raw, value)
    return load_relocation_inputs(raw)


def verify_inputs(inputs: BoundRelocation) -> RelocationProfile:
    if type(inputs) not in (BoundRelocation, HandRelocationInputs):
        raise ValueError("Exact source or analytical relocation input required")
    expected = load_run_inputs(inputs.frozen_bytes)
    require_same_authority(inputs, expected)
    return expected.profile
