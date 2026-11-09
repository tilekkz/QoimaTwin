"""Whole publication identity binds explicit clocks and exact physical input authority."""

from dataclasses import replace
from fractions import Fraction

import pytest

from app.v3.whole_run_inputs import freeze_hand_inputs, load_whole_inputs, verify_inputs
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def test_clock_envelope_roundtrip_and_changed_cap_identity() -> None:
    profile, conveyor = whole_hand_profile(), receipt_conveyor()
    first = freeze_hand_inputs(profile, conveyor, 60 * SECOND, 80 * SECOND)
    restored = load_whole_inputs(first.frozen_bytes)
    assert restored.input_hash == first.input_hash
    assert restored.profile == profile
    second = freeze_hand_inputs(profile, conveyor, 60 * SECOND, 81 * SECOND)
    assert second.input_hash != first.input_hash
    assert second.physical_input_hash == first.physical_input_hash
    verify_inputs(first)


def test_numeric_equal_typed_profile_substitution_is_rejected() -> None:
    inputs = freeze_hand_inputs(whole_hand_profile(), receipt_conveyor(), 60 * SECOND, 80 * SECOND)
    altered = replace(inputs.profile, pickup_tick=True)
    with pytest.raises(ValueError, match=r"typed|type"):
        verify_inputs(replace(inputs, profile=altered))


@pytest.mark.parametrize("horizon,end", [(True, 80 * SECOND), (0, 80), (80, 79)])
def test_invalid_explicit_clock_is_rejected(horizon: int, end: int) -> None:
    with pytest.raises(ValueError, match=r"clock"):
        freeze_hand_inputs(whole_hand_profile(), receipt_conveyor(), horizon, end)


def test_conveyor_value_must_match_source_not_just_its_types() -> None:
    conveyor = replace(receipt_conveyor(), speed_m_s=Fraction(99))
    with pytest.raises(ValueError, match=r"conveyor"):
        freeze_hand_inputs(whole_hand_profile(), conveyor, 60 * SECOND, 80 * SECOND)


def test_decoded_input_object_cannot_mutate_the_cached_source_authority() -> None:
    inputs = freeze_hand_inputs(whole_hand_profile(), receipt_conveyor(), 60 * SECOND, 80 * SECOND)
    original = inputs.profile.pickup_tick
    try:
        object.__setattr__(inputs.profile, "pickup_tick", 2 * original)
        restored = load_whole_inputs(inputs.frozen_bytes)
        assert restored.profile.pickup_tick == original
    finally:
        object.__setattr__(inputs.profile, "pickup_tick", original)
