"""N1 publication binds its extension and rejects forged metadata or native state."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.v3.coordinator_run_projection import project_outcome as project_coordinator
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_run import build_relocation_run, validate_relocation_run
from app.v3.relocation_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def test_actual_paid_transfer_has_an_independent_strict_publication_boundary() -> None:
    profile, conveyor = relocation_hand(), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 10 * SECOND, 20 * SECOND)
    outcome = RelocationEngine(profile, conveyor).run(10 * SECOND, 20 * SECOND)
    run = build_relocation_run(inputs, outcome)
    assert run["schema_version"] == "qoima-relocation-run-0.1.0"
    assert run["outcome_kind"] == "relocation"
    assert run["metrics"]["at_end"]["paid_ticks"] == 13 * SECOND
    assert run["metrics"]["common"]["at_end"]["labor"]["paid_ticks"] == 13 * SECOND
    assert run["input_hash"] == inputs.input_hash
    assert run["outcome"]["at_end"]["relocations"][0]["returned_tick"] == 13 * SECOND
    validate_relocation_run(run, inputs=inputs.frozen_bytes)


@pytest.mark.parametrize("change", ["cost", "return", "scope", "identity", "clock", "unknown"])
def test_recomputed_outer_json_does_not_authorize_changed_native_evidence(change: str) -> None:
    profile, conveyor = relocation_hand(), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 10 * SECOND, 20 * SECOND)
    outcome = RelocationEngine(profile, conveyor).run(10 * SECOND, 20 * SECOND)
    run = deepcopy(build_relocation_run(inputs, outcome))
    if change == "cost":
        run["metrics"]["at_end"]["paid_ticks"] = 0
    elif change == "return":
        run["outcome"]["at_end"]["relocations"][0]["returned_tick"] = 12 * SECOND
    elif change == "scope":
        run["outcome_kind"] = "base_noop"
    elif change == "identity":
        run["input_hash"] = "0" * 64
    elif change == "clock":
        run["horizon_tick"] = True
    else:
        run["ignored"] = 1
    with pytest.raises(ValueError):
        validate_relocation_run(run, inputs=inputs.frozen_bytes)


def test_noop_keeps_original_coordinator_payload_in_an_explicit_new_envelope() -> None:
    profile, conveyor = replace(relocation_hand(), jobs=()), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, SECOND, 2 * SECOND)
    outcome = RelocationEngine(profile, conveyor).run(SECOND, 2 * SECOND)
    run = build_relocation_run(inputs, outcome)
    assert run["outcome_kind"] == "base_noop"
    assert run["outcome"] == project_coordinator(profile.coordinator, outcome)
    validate_relocation_run(run, inputs=inputs.frozen_bytes)


def test_full_input_authority_changes_identity_even_for_equal_physical_operations() -> None:
    profile, conveyor = relocation_hand(), receipt_conveyor()
    changed = replace(profile, provenance=profile.provenance + " / independently named input")
    before = freeze_hand_inputs(profile, conveyor, 10 * SECOND, 20 * SECOND)
    after = freeze_hand_inputs(changed, conveyor, 10 * SECOND, 20 * SECOND)
    outcome = RelocationEngine(profile, conveyor).run(10 * SECOND, 20 * SECOND)
    left, right = build_relocation_run(before, outcome), build_relocation_run(after, outcome)
    assert left["run_id"] != right["run_id"]
    with pytest.raises(ValueError):
        validate_relocation_run(right, inputs=before.frozen_bytes)
