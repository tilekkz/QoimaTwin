"""Analytical input authority for strict C publication; no source permission is inferred."""

from dataclasses import replace
from typing import cast

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_run_inputs import freeze_hand_inputs, load_run_inputs, verify_inputs
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_two_cart_hand_input_freezes_all_resources_without_private_graph_fields() -> None:
    profile = multi_profile(candidate=False, two_carts=True)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 84 * SECOND, 84 * SECOND)
    value = parse_json(inputs.frozen_bytes)
    assert value["scope"] == "analytical_fixture"
    assert len(value["profile"]["unit_resources"]["carts"]) == 2
    assert set(value["profile"]["world"]["receipts"]["flow"]["graph"]) == {
        "graph_id",
        "node_ids",
        "arcs",
    }
    restored = load_run_inputs(inputs.frozen_bytes)
    assert restored.frozen_bytes == inputs.frozen_bytes
    assert restored.input_hash == inputs.input_hash
    assert verify_inputs(restored).registry.registry_common_hash == inputs.registry_common_hash


def test_retained_numeric_equal_clock_and_changed_identity_are_rejected() -> None:
    profile = multi_profile(candidate=False, two_carts=True)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 84 * SECOND, 84 * SECOND)
    for wrong in (
        replace(inputs, horizon_tick=cast(int, True)),
        replace(inputs, input_hash="a" * 64),
        replace(inputs, registry_common_hash="b" * 64),
    ):
        with pytest.raises(ValueError):
            verify_inputs(wrong)


def test_analytical_input_cannot_drop_conveyor_source_binding() -> None:
    profile = multi_profile(candidate=False, two_carts=True)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 84 * SECOND, 84 * SECOND)
    value = parse_json(inputs.frozen_bytes)
    del value["conveyor"]
    with pytest.raises(ValueError):
        load_run_inputs(canonical_bytes(value))


def test_namespace3_unit_publication_has_no_implicit_singleton_resource_fallback() -> None:
    profile = replace(multi_profile(), unit_resources=None)
    with pytest.raises(ValueError, match="explicit unit resources"):
        freeze_hand_inputs(profile, receipt_conveyor(), 300 * SECOND, 400 * SECOND)
