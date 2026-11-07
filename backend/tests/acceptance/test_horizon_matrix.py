"""Input boundary matrix: arrivals are strictly before H, independent of drain."""

from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine, RunStatus, Termination
from tests.builders import fixture_order, run_inputs, scenario

pytestmark = pytest.mark.acceptance


@pytest.mark.parametrize("offset_ticks", [-1, 0, 1])
@pytest.mark.parametrize("drain_s", [0, 0.000001, 60])
def test_arrival_horizon_and_drain_matrix(
    bundle: ContractBundle, contracts_dir: Path, offset_ticks: int, drain_s: float
) -> None:
    # Speed1m/s makes all primitive durations representable at exactly1,000,000ticks/s.
    # Input contract Scenario._consistent rejects arrival>=H, even with a drain window.
    arrival = (1_000_000 + offset_ticks) / 1_000_000
    order = fixture_order(arrival)
    if offset_ticks >= 0:
        with pytest.raises(ValueError, match="arrivals at or after horizon"):
            scenario([order], horizon_s=1)
        return
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([order], horizon_s=1),
        walk_speed_mps=1,
        max_drain_s=drain_s,
    )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    assert engine.ctx.grid.ticks_per_second == 1_000_000
    assert outcome.horizon_tick == 1_000_000
    assert outcome.end_tick == 1_000_000 + round(drain_s * 1_000_000)
    assert outcome.status is RunStatus.PARTIAL
    assert outcome.termination is Termination.MAX_DRAIN
    assert outcome.subsystems["orders"].arrived_total == 1
    assert outcome.subsystems["orders"].completed_total == 0
    assert outcome.subsystems["orders"].pending_total == 1
