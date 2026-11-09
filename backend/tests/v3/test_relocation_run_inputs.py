"""Analytical publication inputs bind base bytes, clocks, authority and independently paid plans."""

from copy import deepcopy
from hashlib import sha256

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_run_inputs import freeze_hand_inputs as freeze_coordinator
from app.v3.relocation_run_inputs import (
    HandRelocationInputs,
    freeze_hand_inputs,
    load_run_inputs,
    verify_inputs,
)
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def test_hand_input_keeps_common_bytes_and_exact_five_step_arithmetic() -> None:
    profile, conveyor = relocation_hand(), receipt_conveyor()
    frozen = freeze_hand_inputs(profile, conveyor, 10 * SECOND, 20 * SECOND)
    common = freeze_coordinator(profile.coordinator, conveyor, 10 * SECOND, 20 * SECOND)
    assert type(frozen) is HandRelocationInputs
    assert frozen.common_inputs == common.frozen_bytes
    assert frozen.input_hash == sha256(frozen.frozen_bytes).hexdigest()
    assert tuple(step.duration for step in frozen.plans[0].steps) == tuple(
        seconds * SECOND for seconds in (2, 2, 3, 1, 5)
    )
    assert load_run_inputs(frozen.frozen_bytes) == frozen
    assert verify_inputs(frozen) == profile


@pytest.mark.parametrize("change", ["plan", "grant", "boolean_clock", "unknown"])
def test_self_consistent_outer_bytes_cannot_forge_inner_hand_authority(change: str) -> None:
    frozen = freeze_hand_inputs(relocation_hand(), receipt_conveyor(), 10 * SECOND, 20 * SECOND)
    value = deepcopy(parse_json(frozen.frozen_bytes))
    if change == "plan":
        value["plans"][0]["steps"][-1]["duration"] = 0
    elif change == "grant":
        value["choices"]["permitted_actor_ids"] = []
    elif change == "boolean_clock":
        value["common_inputs"]["horizon_tick"] = True
    else:
        value["unexpected"] = 1
    with pytest.raises(ValueError):
        load_run_inputs(canonical_bytes(value))


def test_retained_mutable_alias_is_rejected_against_frozen_input() -> None:
    frozen = freeze_hand_inputs(relocation_hand(), receipt_conveyor(), 10 * SECOND, 20 * SECOND)
    object.__setattr__(frozen.choices, "permitted_actor_ids", ["S01"])
    with pytest.raises(ValueError, match=r"type|authority"):
        verify_inputs(frozen)


def test_future_arrival_is_not_admitted_by_the_publication_horizon() -> None:
    profile = relocation_hand()
    object.__setattr__(profile.jobs[0], "arrival_tick", 10 * SECOND)
    with pytest.raises(ValueError, match=r"horizon|HORIZON"):
        freeze_hand_inputs(profile, receipt_conveyor(), 10 * SECOND, 20 * SECOND)
