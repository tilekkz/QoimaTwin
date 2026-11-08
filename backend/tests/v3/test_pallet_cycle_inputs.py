"""Unsupported source identities and timing declarations fail before execution."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_engine import PalletCycleEngine
from app.v3.pallet_cycle_types import PhysicalPallet
from tests.v3.test_pallet_cycle_clock import SOURCE, timing
from tests.v3.test_pallet_cycle_engine import engine, job
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture


def test_unknown_proof_object_is_a_domain_rejection() -> None:
    hu = PhysicalPallet("physical-PALLET-1", "PALLET_LOAD", 24, F(455), "0" * 64)
    with pytest.raises(ValueError, match="proof"):
        PalletCycleEngine(timing(), (), hu, SOURCE, cast(LocalGeometryProof, object()))


@pytest.mark.parametrize("case", ["duplicate", "unknown_hu", "negative_ready", "bool_ready"])
def test_invalid_jobs_are_rejected(proven: LocalGeometryProof, case: str) -> None:
    requests = (job("A"), job("A")) if case == "duplicate" else (job("A"),)
    if case == "unknown_hu":
        requests = (replace(job("A"), hu_id="other"),)
    elif case == "negative_ready":
        requests = (job("A", -1),)
    elif case == "bool_ready":
        requests = (job("A", True),)
    with pytest.raises(ValueError):
        engine(proven, requests)


@pytest.mark.parametrize("limits", [(-1, 1), (2, 1), (False, 1), (1, True)])
def test_observation_limits_are_explicit_integer_ticks(
    proven: LocalGeometryProof, limits: tuple[int, int]
) -> None:
    simulation = engine(proven, ())
    with pytest.raises(ValueError):
        simulation.run(*limits)


def test_empty_demand_keeps_existing_physical_hu_and_zero_actor_exposure(
    proven: LocalGeometryProof,
) -> None:
    result = engine(proven, ()).run(10_000_000, 20_000_000)
    assert result.at_end.tick == 0
    assert result.at_horizon.status == "complete"
    assert result.at_horizon.owner.hu_id == "physical-PALLET-1"
    assert result.at_horizon.owner.kind == "platform"
    assert all(ticks == 0 for _, ticks in result.at_horizon.actor_busy_ticks)
    assert result.events == ()
