"""N1 comparison admission must not conceal any change outside relocation jobs."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.relocation_models import BoundRelocation, RelocationProfile
from app.v3.relocation_pair_inputs import (
    PAIR_POLICY_VERSION,
    PAIR_VERSION,
    load_relocation_pair_inputs,
    prepare_relocation_pair,
    verify_relocation_pair,
)
from app.v3.relocation_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def freeze(profile: RelocationProfile, *, end: int = 20 * SECOND) -> BoundRelocation:
    return freeze_hand_inputs(profile, receipt_conveyor(), 10 * SECOND, end)


@pytest.fixture
def inputs() -> tuple[BoundRelocation, BoundRelocation]:
    profile = relocation_hand()
    return freeze(replace(profile, jobs=())), freeze(profile)


def test_n1_binds_both_complete_inputs_with_independent_paid_plan(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    baseline, candidate = inputs
    pair = prepare_relocation_pair(baseline, candidate, scenario="N1")
    assert pair.scenario == "N1" and pair.baseline.plans == ()
    assert tuple(s.duration for s in pair.candidate.plans[0].steps) == tuple(
        n * SECOND for n in (2, 2, 3, 1, 5)
    )
    assert pair.common_input_hash == sha256(baseline.common_inputs).hexdigest()
    assert pair.input_hash == sha256(pair.frozen_bytes).hexdigest()
    value = parse_json(pair.frozen_bytes)
    assert value["schema_version"] == PAIR_VERSION
    assert value["policy_version"] == PAIR_POLICY_VERSION
    assert canonical_bytes(value["baseline_inputs"]) == baseline.frozen_bytes
    assert canonical_bytes(value["candidate_inputs"]) == candidate.frozen_bytes
    loaded = load_relocation_pair_inputs(pair.frozen_bytes)
    assert loaded.baseline.frozen_bytes == baseline.frozen_bytes
    assert loaded.candidate.frozen_bytes == candidate.frozen_bytes
    assert verify_relocation_pair(pair) == loaded


def test_zero_job_candidate_is_an_admissible_noop(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    baseline, _ = inputs
    pair = prepare_relocation_pair(baseline, baseline, scenario="N1")
    assert pair.baseline.frozen_bytes == pair.candidate.frozen_bytes
    assert pair.baseline.plans == pair.candidate.plans == ()


@pytest.mark.parametrize("scenario", ["N0", "N4", "n1", True, None])
def test_only_explicit_n1_scenario_is_accepted(
    inputs: tuple[BoundRelocation, BoundRelocation], scenario: object
) -> None:
    with pytest.raises(ValueError, match="SCENARIO"):
        prepare_relocation_pair(*inputs, scenario=scenario)


def test_baseline_cannot_already_contain_the_relocation(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    with pytest.raises(ValueError, match="BASELINE"):
        prepare_relocation_pair(inputs[1], inputs[1], scenario="N1")


def test_different_valid_end_caps_cannot_enter_the_same_pair(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    candidate = freeze(relocation_hand(), end=21 * SECOND)
    with pytest.raises(ValueError, match="COMMON"):
        prepare_relocation_pair(inputs[0], candidate, scenario="N1")


def test_actor_speed_drift_is_rejected_even_when_both_profiles_are_valid(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    profile = relocation_hand()
    common = profile.coordinator
    flow = common.world.receipts.flow
    actors = tuple(replace(a, speed_m_s=F(2)) if a.actor_id == "S01" else a for a in flow.actors)
    world = replace(
        common.world, receipts=replace(common.world.receipts, flow=replace(flow, actors=actors))
    )
    candidate = freeze(replace(profile, coordinator=replace(common, world=world)))
    with pytest.raises(ValueError, match="COMMON"):
        prepare_relocation_pair(inputs[0], candidate, scenario="N1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("profile_id", "different-profile"),
        ("provenance", "different provenance"),
        ("permitted_actor_ids", ("S01", "S02")),
        ("min_width_m", F(9, 10)),
        ("min_height_m", F(9, 10)),
    ],
)
def test_all_nonjob_choices_must_remain_identical(
    inputs: tuple[BoundRelocation, BoundRelocation], field: str, value: Any
) -> None:
    candidate = freeze(replace(relocation_hand(), **{field: value}))
    with pytest.raises(ValueError, match="CHOICES"):
        prepare_relocation_pair(inputs[0], candidate, scenario="N1")


def test_valid_place_metadata_cannot_drift_between_arms(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    profile = relocation_hand()
    places = tuple(replace(p, module_max_gross_kg=F(101)) for p in profile.places)
    candidate = freeze(replace(profile, places=places))
    with pytest.raises(ValueError, match="PLACES"):
        prepare_relocation_pair(inputs[0], candidate, scenario="N1")


def test_source_and_analytical_input_types_cannot_be_mixed(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    right = inputs[1]
    source_label = BoundRelocation(
        right.profile,
        right.plans,
        right.choices,
        right.common_inputs,
        right.frozen_bytes,
        right.input_hash,
    )
    with pytest.raises(ValueError, match="FAMILY"):
        prepare_relocation_pair(inputs[0], source_label, scenario="N1")


def test_retained_inner_metadata_must_match_its_own_canonical_inputs(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    candidate = replace(inputs[1], input_hash="0" * 64)
    with pytest.raises(ValueError):
        prepare_relocation_pair(inputs[0], candidate, scenario="N1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario", "N4"),
        ("policy_version", "unknown"),
        ("input_family", "source_bound"),
        ("baseline_input_hash", "0" * 64),
        ("common_input_hash", True),
        ("unexpected", 0),
    ],
)
def test_rehashed_pair_metadata_cannot_relabel_verified_inputs(
    inputs: tuple[BoundRelocation, BoundRelocation], field: str, value: object
) -> None:
    pair = prepare_relocation_pair(*inputs, scenario="N1")
    payload = deepcopy(parse_json(pair.frozen_bytes))
    payload[field] = value
    with pytest.raises(ValueError):
        load_relocation_pair_inputs(canonical_bytes(payload))


def test_retained_pair_fields_and_exact_byte_type_are_checked(
    inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    pair = prepare_relocation_pair(*inputs, scenario="N1")
    with pytest.raises(ValueError):
        verify_relocation_pair(replace(pair, common_input_hash="0" * 64))
    with pytest.raises(ValueError):
        load_relocation_pair_inputs(bytearray(pair.frozen_bytes))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        load_relocation_pair_inputs(pair.frozen_bytes + b"\n")
