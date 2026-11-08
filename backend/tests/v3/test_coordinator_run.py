"""Strict C native publication keeps source identity and every mutable physical resource."""

from copy import deepcopy

import pytest

from app.v3.coordinator_run import build_coordinator_run, validate_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_coordinator_run_inventory import inventory_case
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_role_only_native_run_has_separate_business_resource_observation_boundaries() -> None:
    profile, outcome = role_case(200 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 200 * SECOND, 200 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    assert run["input_hash"] == inputs.input_hash
    assert run["engine_version"] == "qoima-staff-coordinator-v3-proposal-3"
    assert run["metrics"]["completion"]["business_complete_tick"] == 0
    assert run["metrics"]["completion"]["resource_drained_tick"] == 160 * SECOND
    assert run["observed_until_tick"] == 200 * SECOND
    validate_coordinator_run(run, inputs=inputs.frozen_bytes)


def test_native_run_keeps_both_unit_cycles_and_exact_input_binding() -> None:
    profile, outcome = inventory_case()
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 300 * SECOND, 400 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    assert run["metrics"]["at_horizon"]["unit"]["completed_units"] == 3
    assert run["metrics"]["at_end"]["unit"]["completed_units"] == 6
    wrong = deepcopy(run)
    wrong["registry_common_hash"] = "f" * 64
    with pytest.raises(ValueError):
        validate_coordinator_run(wrong, inputs=inputs.frozen_bytes)


def test_compact_snapshot_cannot_invent_paid_labor_or_drop_actual_cart() -> None:
    profile, outcome = role_case(200 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 200 * SECOND, 200 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    for field, value in (("carts", []), ("role_bindings", [["PK05", "P01"]])):
        wrong = deepcopy(run)
        wrong["outcome"]["at_end"][field] = value
        with pytest.raises(ValueError):
            validate_coordinator_run(wrong, inputs=inputs.frozen_bytes)
