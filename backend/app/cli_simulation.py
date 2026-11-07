"""Simulation command implementation; inputs are persisted before the engine starts."""

from importlib import import_module
from pathlib import Path
from typing import Any

from app.contracts.loader import ContractBundle
from app.contracts.runtime_inputs import load_assignment
from app.data.scenario_materializer import Profile, materialize, write_materialized
from app.exporter.identity import fingerprint
from app.exporter.run import export_run, write_run
from app.simulation.context import RunInputs
from app.simulation.engine import Engine, RunOutcome
from app.simulation.metrics_summary import summary


def simulate(
    bundle: ContractBundle,
    profile: Profile,
    horizon_s: int,
    out_dir: Path,
    assignment_path: Path | None = None,
    output_format: str = "v2",
    include_inline: bool = False,
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
    run = _publish(engine, outcome, out_dir, output_format, include_inline)
    return {
        "status": run["status"],
        "run_id": run["run_id"],
        "termination_reason": run["termination_reason"],
        "shortened_run": horizon_s < 3600,
    }


def _publish(
    engine: Engine, outcome: RunOutcome, out_dir: Path, output_format: str, include_inline: bool
) -> dict[str, Any]:
    inputs = engine.ctx.inputs
    exporter, writer = export_run, write_run
    options: dict[str, Any] = {}
    if output_format == "proposal":
        proposal = import_module("app.exporter.proposal")
        exporter, writer = proposal.export_proposal, proposal.write_proposal_run
        options["include_inline"] = include_inline
    elif output_format != "v2":
        raise ValueError("unsupported simulation output format")
    run = exporter(engine, outcome, validate=False)
    writer(
        run,
        out_dir,
        allow_existing_inputs=True,
        chunk_duration_s=inputs.config.chunk_duration_s,
        snapshot_interval_s=inputs.config.snapshot_interval_s,
        **options,
        metadata={
            "identity": run.get("identity", fingerprint(inputs)),
            "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
            "provenance": inputs.scenario.provenance.model_dump(mode="json"),
            "metrics": summary(engine, outcome),
            "ticks_per_second": engine.ctx.grid.ticks_per_second,
        },
    )
    return run
