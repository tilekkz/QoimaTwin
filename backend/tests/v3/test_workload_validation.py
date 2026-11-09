"""Malformed external policies and typed inputs never produce partial workloads."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import DemandWeight, WorkloadPolicy, WorkloadSource
from app.v3.workload_policy import parse_workload_policy
from tests.v3.test_workload_fixtures import hand_source, policy_document


@pytest.mark.parametrize("invalid", [None, [], True, "normal", 1, float("nan")])
def test_policy_root_requires_an_explicit_object(invalid: object) -> None:
    with pytest.raises(ValueError):
        parse_workload_policy(invalid)


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("offered_hus", {"inbound": 1}),
        ("offered_hus", {"inbound": 1, "outbound": 1, "seed": 0}),
        ("offered_hus", {"inbound": True, "outbound": 1}),
        ("offered_hus", {"inbound": 1, "outbound": float("inf")}),
        ("calendar", {"kind": "peak", "windows": []}),
        ("calendar", {"kind": [], "windows": []}),
        ("calendar", {"kind": "normal", "windows": (), "seed": 0}),
        ("calendar", {"kind": "normal", "windows": ()}),
    ],
)
def test_policy_nested_objects_reject_unknown_fields_and_types(section: str, value: Any) -> None:
    policy = policy_document()
    policy[section] = value
    with pytest.raises(ValueError):
        parse_workload_policy(policy)


@pytest.mark.parametrize(
    "weight", [None, 1, (), [], [1], [1, 1, 1], [0, 1], [1, 0], [True, 1], [1, 1.0], [1, -1]]
)
def test_burst_rationals_require_two_positive_exact_integer_tokens(weight: object) -> None:
    policy = policy_document()
    policy["calendar"] = {
        "kind": "burst",
        "windows": [{"start_tick": 0, "end_tick": 10, "weight": weight}],
    }
    with pytest.raises(ValueError):
        parse_workload_policy(policy)


def malformed_source(case: str) -> WorkloadSource:
    source = hand_source()
    if case == "fingerprint":
        return replace(source, raw_fingerprints=(("hand-source", "invalid"),))
    if case == "inventory":
        return replace(source, document_fingerprints=(("other", "b" * 64),))
    if case == "sku_reference":
        return replace(source, inbound_weights=(DemandWeight("missing", "IN1", F(1)),))
    if case == "duplicate_pair":
        return replace(source, inbound_weights=source.inbound_weights * 2)
    template = source.templates[0]
    if case == "duplicate_hu":
        template = replace(template, initial_hu_ids=source.templates[1].initial_hu_ids)
    elif case == "dimensions":
        template = replace(template, dimensions_xyz_m=(F(0), F(1), F(1)))
    elif case == "recipe":
        template = replace(template, packing_recipe_sha256="bad")
    elif case == "quantity":
        template = replace(template, quantity_units=True)
    else:
        template = replace(template, orientation_id="invented_orientation")
    return replace(source, templates=(template, source.templates[1]))


@pytest.mark.parametrize(
    "case",
    [
        "fingerprint",
        "inventory",
        "sku_reference",
        "duplicate_pair",
        "duplicate_hu",
        "dimensions",
        "recipe",
        "quantity",
        "orientation",
    ],
)
def test_invalid_source_is_rejected_even_for_zero_offered_budget(case: str) -> None:
    with pytest.raises(ValueError):
        materialize_workload(malformed_source(case), WorkloadPolicy(10, 0, 0, "normal"))


def test_source_provenance_and_population_counts_bind_both_identity_hashes() -> None:
    source, policy = hand_source(), WorkloadPolicy(10, 1, 1, "normal")
    original = materialize_workload(source, policy)
    changed_source = replace(source, raw_fingerprints=(("hand-source", "f" * 64),))
    changed = materialize_workload(changed_source, policy)
    changed_count = materialize_workload(source, replace(policy, inbound_hus=2))
    changed_horizon = materialize_workload(source, replace(policy, horizon_tick=20))
    assert original.population_id != changed.population_id != changed_count.population_id
    assert original.workload_id != changed.workload_id != changed_count.workload_id
    assert original.population_id == changed_horizon.population_id
    assert original.workload_id != changed_horizon.workload_id
