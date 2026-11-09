"""Source-only N1 admission retains identical source authority before any engine exists."""

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from app.storage.canonical_json import parse_json
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.coordinator_profile_authority import authoritative_sources
from app.v3.relocation_binding import bind_relocation_source, decode_relocation_choices
from app.v3.relocation_models import BoundRelocation
from app.v3.relocation_pair_inputs import prepare_relocation_pair

COMMON_HASH = "47ea8d54101f63b7dd2f958a41174c716607019a6f43a7379d2b80b3f42b3f99"
CANDIDATE_HASH = "a613b189fa64fac9f4544d0434e387d760c2735faccef7d767287e760e66d57a"


@pytest.fixture(scope="module")
def source_inputs() -> tuple[BoundRelocation, BoundRelocation]:
    root = Path(__file__).resolve().parents[2] / "docs/proposals/adaptive-v3"
    bundle, conveyor = authoritative_sources()
    common = compile_coordinator_profile(
        bundle, conveyor, json.loads((root / "coordinator-profile.example.json").read_bytes())
    )
    choices = decode_relocation_choices(
        json.loads((root / "relocation-n1-single.example.json").read_bytes())
    )
    baseline = bind_relocation_source(common.frozen_bytes, replace(choices, jobs=()))
    candidate = bind_relocation_source(common.frozen_bytes, choices)
    return baseline, candidate


def test_zero_job_source_retains_every_place_and_exact_common_bytes(
    source_inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    baseline, candidate = source_inputs
    assert baseline.profile.jobs == ()
    assert baseline.plans == ()
    assert len(baseline.profile.places) == len(candidate.profile.places) == 776
    assert baseline.profile.places == candidate.profile.places
    assert baseline.common_inputs == candidate.common_inputs
    assert sha256(baseline.common_inputs).hexdigest() == COMMON_HASH
    assert candidate.input_hash == CANDIDATE_HASH


def test_source_pair_is_prepared_without_changing_initial_stock_or_common_inputs(
    source_inputs: tuple[BoundRelocation, BoundRelocation],
) -> None:
    pair = prepare_relocation_pair(*source_inputs, scenario="N1")
    assert pair.common_input_hash == COMMON_HASH
    assert parse_json(pair.frozen_bytes)["input_family"] == "source_bound"
    left = pair.baseline.profile.coordinator.world.receipts.flow.stock
    right = pair.candidate.profile.coordinator.world.receipts.flow.stock
    assert left == right
    assert len(left.containers) == 530 and len(left.units) == 12_256
    assert pair.candidate.input_hash == CANDIDATE_HASH
