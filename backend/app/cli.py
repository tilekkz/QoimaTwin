"""Command-line entry point: `uv run python -m app.cli <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from jsonschema import ValidationError as SchemaValidationError

from app.contracts.loader import ContractError, load_contract_bundle
from app.contracts.validation import validate_bundle
from app.conveyor.topology import ConveyorTopology, TopologyError
from app.data.scenario_materializer import Profile, materialize, write_materialized
from app.navigation.shortest_paths import AllPairsPaths
from app.settings import default_contracts_dir
from app.version import ENGINE_VERSION


def _simulate(profile: Profile, horizon_s: int, out_dir: Path) -> int:
    from app.contracts.assignment import Assignment
    from app.exporter.identity import fingerprint
    from app.exporter.run import export_run, write_run
    from app.simulation.context import RunInputs
    from app.simulation.engine import Engine
    from app.simulation.invariants import InvariantViolation
    from app.simulation.metrics_summary import summary

    try:
        bundle = load_contract_bundle(default_contracts_dir())
        materialized = materialize(profile, horizon_s, bundle.config)
        write_materialized(materialized, out_dir / "inputs")
        assignment = Assignment.from_json_text(
            (bundle.directory / "assignment.example.json").read_bytes()
        )
        inputs = RunInputs(
            bundle.layout, bundle.config, bundle.actors, assignment, materialized.scenario
        )
        engine = Engine(inputs, check_invariants=True)
        outcome = engine.run()
        run = export_run(engine, outcome)
        write_run(
            run,
            out_dir,
            metadata={
                "identity": fingerprint(inputs),
                "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
                "provenance": inputs.scenario.provenance.model_dump(mode="json"),
                "metrics": summary(engine, outcome),
                "ticks_per_second": engine.ctx.grid.ticks_per_second,
            },
        )
    except (ContractError, ValueError, OSError, SchemaValidationError, InvariantViolation) as exc:
        print(json.dumps({"status": "failed", "issues": [str(exc)]}))
        return 1
    print(
        json.dumps(
            {
                "status": run["status"],
                "run_id": run["run_id"],
                "termination_reason": run["termination_reason"],
            }
        )
    )
    return 0


def _validate_contracts(contracts_dir: Path) -> int:
    report: dict[str, object] = {
        "engine_version": ENGINE_VERSION,
        "contracts_dir": str(contracts_dir),
    }
    try:
        bundle = load_contract_bundle(contracts_dir)
        issues = validate_bundle(bundle)
        if issues:
            report |= {"status": "failed", "issues": issues}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1
        topology = ConveyorTopology.from_layout(bundle.layout)
        paths = AllPairsPaths.from_graph(bundle.layout.picker_graph)
    except (ContractError, TopologyError) as exc:
        report |= {"status": "failed", "issues": [str(exc)]}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    report |= {
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "summary": {
            "layout_version": bundle.layout.layout_version,
            "picker_nodes": len(paths.node_ids),
            "picker_edges": len(bundle.layout.picker_graph.edges),
            "slots": len(bundle.layout.slots),
            "conveyor_cells": len(topology.cells),
            "actors": len(bundle.actors.actors),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


def _materialize(profile: Profile, horizon_s: int, out_dir: Path) -> int:
    try:
        config = load_contract_bundle(default_contracts_dir()).config
        result = materialize(profile, horizon_s, config)
        write_materialized(result, out_dir)
    except (ContractError, ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "issues": [str(exc)]}))
        return 1
    print(json.dumps({"status": "passed", "scenario_id": result.scenario.scenario_id}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qoima", description="QoimaTwin backend tools")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-contracts", help="check shared contract files")
    validate.add_argument("--contracts-dir", type=Path, default=None)
    materializer = commands.add_parser("materialize", help="write a synthetic scenario and history")
    materializer.add_argument(
        "--profile", choices=("large-normal", "large-peak", "promotion"), required=True
    )
    materializer.add_argument("--horizon-s", type=int, required=True)
    materializer.add_argument("--out", type=Path, required=True)
    simulator = commands.add_parser("simulate", help="simulate and export a validated run bundle")
    simulator.add_argument(
        "--profile", choices=("large-normal", "large-peak", "promotion"), required=True
    )
    simulator.add_argument("--horizon-s", type=int, required=True)
    simulator.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-contracts":
        return _validate_contracts(args.contracts_dir or default_contracts_dir())
    if args.command == "materialize":
        return _materialize(args.profile, args.horizon_s, args.out)
    if args.command == "simulate":
        return _simulate(args.profile, args.horizon_s, args.out)
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":
    sys.exit(main())
