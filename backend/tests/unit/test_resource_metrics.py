"""Time-weighted resource measurements from explicit samples, not run-derived values."""

from pathlib import Path

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from tests.builders import run_inputs, scenario
from tests.flow_builders import flow_engine, full_pack, through


def test_resource_integrals_and_minima(bundle: ContractBundle, contracts_dir: Path) -> None:
    from app.simulation.observations import ResourceSample
    from app.simulation.resource_metrics import resource_summary

    engine = Engine(run_inputs(bundle, contracts_dir, scenario([])), check_invariants=True)
    tps = engine.ctx.grid.ticks_per_second
    engine.observer.samples = [
        ResourceSample(0, 2, 1, 94),
        ResourceSample(3 * tps, 4, 0, 92),
        ResourceSample(7 * tps, 0, 0, 96),
    ]
    result = resource_summary(engine, 10 * tps)
    assert result["conveyor_metrics"]["occupied_cells_mean"] == 2.2  # (2*3+4*4)/10
    assert result["conveyor_metrics"]["jam_duration_s"] == 3
    assert result["conveyor_metrics"]["blocked_cargo_seconds"] == 3
    assert result["tote_metrics"]["free_mean"] == 93.8  # (94*3+92*4+96*3)/10
    assert result["tote_metrics"]["free_min"] == 92


def test_samples_at_cutoff_have_zero_weight(bundle: ContractBundle, contracts_dir: Path) -> None:
    from app.simulation.observations import ResourceSample
    from app.simulation.resource_metrics import resource_summary

    engine = Engine(run_inputs(bundle, contracts_dir, scenario([])), check_invariants=True)
    tps = engine.ctx.grid.ticks_per_second
    engine.observer.samples = [ResourceSample(0, 0, 0, 96), ResourceSample(10 * tps, 1, 1, 0)]
    result = resource_summary(engine, 10 * tps)
    assert result["conveyor_metrics"]["jam_duration_s"] == 0
    assert result["tote_metrics"]["free_min"] == 96
    assert result["tote_metrics"]["unavailable_s"] == 0


def test_capacity_jam_clears_when_service_opens_the_post(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    from app.simulation.resource_metrics import resource_summary

    engine = flow_engine(bundle, contracts_dir, pack_s=5)
    full_pack(engine)
    engine.observer.observe(0, engine.ctx.ticks(1))
    occupancy, cursors = dict(engine.conveyor.occupancy), dict(engine.conveyor.cursors)
    engine.observer._jammed()
    assert engine.conveyor.occupancy == occupancy
    assert engine.conveyor.cursors == cursors
    through(engine, 6)
    belt = resource_summary(engine, engine.ctx.ticks(6))["conveyor_metrics"]
    assert belt["jam_duration_s"] == 5  # two totes blocked by full pack buffer on [0,5).
    assert belt["blocked_cargo_seconds"] == 10
