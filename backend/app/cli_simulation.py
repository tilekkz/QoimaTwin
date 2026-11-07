"""Simulation command implementation; inputs are persisted before the engine starts."""

from pathlib import Path
from typing import Any

from app.contracts.loader import ContractBundle
from app.contracts.runtime_inputs import load_assignment
from app.data.scenario_materializer import Profile, materialize, write_materialized
from app.exporter.identity import fingerprint
from app.exporter.run import export_run, write_run
from app.simulation.context import RunInputs
from app.simulation.engine import Engine
from app.simulation.metrics_summary import summary


def simulate(
    bundle: ContractBundle,
    profile: Profile,
    horizon_s: int,
    out_dir: Path,
    assignment_path: Path | None = None,
) -> dict[str, Any]:
    materialized = materialize(profile, horizon_s, bundle.config)
    path = assignment_path or bundle.directory / "assignment.example.json"
    assignment = load_assignment(path, bundle.layout)
    inputs = RunInputs(
        bundle.layout, bundle.config, bundle.actors, assignment, materialized.scenario
    )
    engine = Engine(inputs, check_invariants=True)
    write_materialized(materialized, out_dir / "inputs")
    outcome = engine.run()
    run = export_run(engine, outcome, validate=False)
    write_run(
        run,
        out_dir,
        allow_existing_inputs=True,
        chunk_duration_s=bundle.config.chunk_duration_s,
        snapshot_interval_s=bundle.config.snapshot_interval_s,
        metadata={
            "identity": fingerprint(inputs),
            "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
            "provenance": inputs.scenario.provenance.model_dump(mode="json"),
            "metrics": summary(engine, outcome),
            "ticks_per_second": engine.ctx.grid.ticks_per_second,
        },
    )
    return {
        "status": run["status"],
        "run_id": run["run_id"],
        "termination_reason": run["termination_reason"],
        "shortened_run": horizon_s < 3600,
    }
