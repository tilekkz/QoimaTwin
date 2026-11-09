"""One exact source compile; no engine, HTTP or source simulation."""

import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.coordinator_profile_authority import authoritative_sources
from app.v3.relocation_binding import (
    INPUT_SCOPE,
    bind_relocation_source,
    decode_relocation_choices,
    load_relocation_inputs,
)
from app.v3.relocation_models import RELOCATION_VERSION, RelocationChoices
from app.v3.whole_profile_geometry import ROUTE_POLICY
from tests.v3.test_relocation_admission import source_job


@pytest.mark.parametrize("choices", [None, [], {}, "invalid"])
def test_malformed_input_envelope_rejects_with_value_error(choices: object) -> None:
    raw = canonical_bytes(
        {
            "schema_version": RELOCATION_VERSION,
            "scope": INPUT_SCOPE,
            "choices": choices,
            "common_input_hash": "invalid",
            "common_inputs": {},
            "places": [],
            "plans": [],
            "route_policy": ROUTE_POLICY,
            "rounding": "invalid",
            "horizon_tick": 0,
            "end_tick": 0,
        }
    )
    with pytest.raises(ValueError):
        load_relocation_inputs(raw)


@pytest.mark.parametrize("numerator", [True, 7.0, "7"])
def test_example_rejects_inexact_rational_components(numerator: object) -> None:
    root = Path(__file__).resolve().parents[2]
    value = json.loads(
        (root / "docs/proposals/adaptive-v3/relocation-n1-single.example.json").read_bytes()
    )
    assert decode_relocation_choices(value).jobs[0].hu_id == "v3:HU:initial:DEMO_113:01"
    value["min_width_m"]["numerator"] = numerator
    with pytest.raises(ValueError, match="Exact integer rational"):
        decode_relocation_choices(value)


def test_source_binding_retains_common_bytes_and_the_precomputed_clock_oracle() -> None:
    root = Path(__file__).resolve().parents[2]
    value = json.loads(
        (root / "docs/proposals/adaptive-v3/coordinator-profile.example.json").read_bytes()
    )
    bundle, belt = authoritative_sources()
    common = compile_coordinator_profile(bundle, belt, value)
    choices = RelocationChoices(
        "source-N1-single",
        "explicit bounded manual choices",
        (source_job(),),
        ("S01",),
        ROUTE_POLICY,
        F(7, 10),
        F(9, 5),
    )
    bound = bind_relocation_source(common.frozen_bytes, choices)
    assert bound.common_inputs == common.frozen_bytes
    assert len(bound.profile.coordinator.world.receipts.flow.actors) == 24
    (plan,) = bound.plans
    assert [step.duration for step in plan.steps] == [
        85_740_000,
        1_000_000,
        93_080_000,
        1_000_000,
        15_340_001,
    ]
    assert plan.gross_mass_kg == F(127, 20) and len(plan.unit_ids) == 24
    assert plan.unit_ids[0] == "v3:HU:initial:DEMO_113:01:unit:0001"
    assert load_relocation_inputs(bound.frozen_bytes).frozen_bytes == bound.frozen_bytes
