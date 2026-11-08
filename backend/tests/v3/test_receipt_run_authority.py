"""Same JSON projection does not authorize a forged typed physical profile."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.v3.flow_profile_wire import record
from app.v3.receipt_run_inputs import verify_frozen
from tests.v3.test_receipt_run_fixtures import sample


def test_fraction_shaped_dictionary_is_not_a_typed_actor_speed() -> None:
    inputs, _ = sample()
    actor = deepcopy(inputs.profile.flow.actors[0])
    object.__setattr__(actor, "speed_m_s", record(actor.speed_m_s))
    flow = replace(inputs.profile.flow, actors=(actor, *inputs.profile.flow.actors[1:]))
    forged = replace(inputs, profile=replace(inputs.profile, flow=flow))
    with pytest.raises(ValueError):
        verify_frozen(forged)
