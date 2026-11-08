"""Prewritten retained-world regressions from independent static review; checks deferred."""

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_shared_engine import PalletSharedEngine
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture
from tests.v3.test_pallet_shared_fixtures import shared_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


@pytest.mark.parametrize("changed", [1_000_000, False])
def test_retained_actor_cannot_change_schedule_under_the_original_profile_digest(
    proven: LocalGeometryProof,
    changed: object,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    engine = PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    original_digest = engine.profile_sha256
    actor = next(a for a in profile.world.receipts.flow.actors if a.actor_id == "F01")
    object.__setattr__(actor, "available_tick", changed)
    assert engine.workers["F01"].spec is actor
    with pytest.raises(RuntimeError, match="world authority"):
        engine._check()
    assert engine.profile_sha256 == original_digest and engine.ledger.history == ()


def test_retained_world_fraction_dictionary_cannot_impersonate_exact_number(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    engine = PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    actor = next(a for a in profile.world.receipts.flow.actors if a.actor_id == "F01")
    object.__setattr__(actor, "speed_m_s", {"numerator": 1, "denominator": 1})
    with pytest.raises(RuntimeError, match="world authority"):
        engine._check()
