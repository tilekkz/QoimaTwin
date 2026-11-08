"""Derived metadata must retain exact JSON types when the native outcome is unchanged."""

from copy import deepcopy
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_run import build_coordinator_run, validate_coordinator_run
from app.v3.coordinator_run_inputs import HandCoordinatorInputs, freeze_hand_inputs
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor

type NativeCase = tuple[HandCoordinatorInputs, dict[str, Any]]


@pytest.fixture(scope="module")
def native_case() -> NativeCase:
    profile, outcome = role_case(200 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 200 * SECOND, 200 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    validate_coordinator_run(run, inputs=inputs.frozen_bytes)
    return inputs, run


def test_valid_native_metadata_is_accepted_without_changing_bytes(native_case: NativeCase) -> None:
    inputs, run = native_case
    before = canonical_bytes(run)
    validate_coordinator_run(run, inputs=inputs.frozen_bytes)
    assert canonical_bytes(run) == before


@pytest.mark.parametrize(
    ("group", "field", "alias"),
    [("resources", "cart_count", True), ("receipts", "pending_putaway", False)],
)
def test_boolean_alias_cannot_replace_numeric_derived_metric(
    native_case: NativeCase, group: str, field: str, alias: bool
) -> None:
    inputs, valid = native_case
    wrong = deepcopy(valid)
    original = wrong["metrics"]["at_end"][group][field]
    assert type(original) is int and original == alias
    wrong["metrics"]["at_end"][group][field] = alias
    assert canonical_bytes(wrong["outcome"]) == canonical_bytes(valid["outcome"])
    assert canonical_bytes(wrong) != canonical_bytes(valid)
    with pytest.raises(ValueError):
        validate_coordinator_run(wrong, inputs=inputs.frozen_bytes)
