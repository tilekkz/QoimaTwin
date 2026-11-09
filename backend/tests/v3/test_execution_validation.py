"""Invalid explicit proposals fail before any physical operation is scheduled."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_types import ExecutionProfile, InitialPlacement
from tests.v3.test_execution_manual import fixture


def invalid_profiles() -> list[ExecutionProfile]:
    profile, _ = fixture()
    hu, port = profile.handling_units[0], profile.ports[0]
    return [
        replace(profile, profile_id=""),
        replace(profile, actors=profile.actors[:-1]),
        replace(profile, actors=(*profile.actors, profile.actors[0])),
        replace(profile, jobs=(*profile.jobs, profile.jobs[0])),
        replace(profile, source_bindings=()),
        replace(profile, graph_sha256="bogus"),
        replace(profile, handling_units=(replace(hu, quantity=True),)),
        replace(profile, handling_units=(replace(hu, gross_mass_kg=F(0)),)),
        replace(profile, handling_units=(replace(hu, dimensions_xyz_m=(F(2),) * 3),)),
        replace(profile, ports=(replace(port, service_ticks=((hu.archetype, True),)),)),
        replace(profile, ports=(replace(port, windows=((5, 2),)),)),
        replace(profile, ports=(replace(port, windows=((0, 5), (4, 6))),)),
        replace(profile, ports=(replace(port, eligible_actor_ids=frozenset({"R03"})),)),
        replace(profile, ports=(replace(port, buffer_places=()),)),
        replace(profile, jobs=(replace(profile.jobs[0], hu_id="unknown"),)),
        replace(profile, initial_placements=(InitialPlacement(hu.hu_id, "slot"),)),
    ]


@pytest.mark.parametrize("profile", invalid_profiles())
def test_malformed_profile_rejects_before_running(profile: ExecutionProfile) -> None:
    _, graph = fixture()
    with pytest.raises(ValueError):
        ManualEngine(profile, graph, check_invariants=True)
