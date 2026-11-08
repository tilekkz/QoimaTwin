"""The target suffix has a loaded precondition, never port credit or initial source stock."""

from fractions import Fraction as F

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_putaway_primitive import compile_putaway_primitive, verify_putaway_primitive
from tests.v3.test_pallet_cycle_clock import SOURCE, timing
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture


def test_proved_suffix_handover_is_3_35_and_safe_return_6_4_seconds(
    proven: LocalGeometryProof,
) -> None:
    value = compile_putaway_primitive(SOURCE, proven, timing(), source_bridge=False)
    assert value.initial_custody == "vehicle:FL01"
    assert value.source_binding == "local_fixture_only"
    assert value.final_custody == "v3:slot:HEAVY_E:001:L1:B1"
    assert value.release_offset_tick == 3_350_000
    assert value.duration_tick == 6_400_000
    assert value.steps[0].phase == "travel_approach" and value.steps[0].attached is True
    assert not any(step.kind == "attach" for step in value.steps)
    assert value.receipt_credit_allowed is False


def test_retained_suffix_cannot_claim_a_different_release_time(
    proven: LocalGeometryProof,
) -> None:
    value = compile_putaway_primitive(SOURCE, proven, timing(), source_bridge=False)
    object.__setattr__(value, "release_offset_tick", 1)
    with pytest.raises(ValueError, match="primitive"):
        verify_putaway_primitive(SOURCE, proven, timing(), value, source_bridge=False)


def test_loaded_bridge_requires_a_new_actual_attached_sweep(
    proven: LocalGeometryProof,
) -> None:
    value = compile_putaway_primitive(SOURCE, proven, timing(), source_bridge=True)
    assert value.loaded_bridge_checks > 0
    assert value.source_binding == "source_prehandle_bound"
    assert value.steps[0].kind == "bridge" and value.steps[0].attached is True
    assert value.steps[-1].kind == "bridge" and value.steps[-1].attached is False
    assert value.bridge is not None and value.bridge.distance_m == F(".05")
    assert value.bridge.entry_cover_checks == value.loaded_bridge_checks
    assert value.release_offset_tick == 3_400_000
    assert value.duration_tick == 6_500_000
    assert value.receipt_credit_allowed is False
