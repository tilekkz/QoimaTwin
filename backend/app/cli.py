"""Command-line entry point with stable JSON errors and explicit execution status."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import ValidationError as SchemaValidationError

from app.cli_simulation import simulate
from app.contracts.loader import ContractBundle, ContractError, load_contract_bundle
from app.contracts.runtime_inputs import validate_config_file
from app.contracts.validation import validate_bundle
from app.conveyor.topology import ConveyorTopology
from app.data.scenario_materializer import materialize, write_materialized
from app.errors import AppError, InvalidInputError, error_report, require_empty_output
from app.navigation.shortest_paths import AllPairsPaths
from app.settings import default_contracts_dir
from app.version import ENGINE_VERSION


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise InvalidInputError(message)


def _horizon(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("horizon must be integer seconds") from exc
    if not 0 < result <= 168 * 3600:
        raise argparse.ArgumentTypeError("horizon must be positive and at most 168 hours")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="qoima", description="QoimaTwin backend tools")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-contracts", help="check shared contract files")
    validate.add_argument("--contracts-dir", type=Path, default=None)
    for name in ("materialize", "simulate"):
        command = commands.add_parser(name, help=f"{name} a synthetic scenario")
        command.add_argument(
            "--profile", choices=("large-normal", "large-peak", "promotion"), required=True
        )
        command.add_argument("--horizon-s", type=_horizon, required=True)
        command.add_argument("--out", type=Path, required=True)
        if name == "simulate":
            command.add_argument("--assignment", type=Path, default=None)
    return parser


def _validate_contracts(bundle: ContractBundle) -> dict[str, Any]:
    issues = validate_bundle(bundle)
    if issues:
        raise InvalidInputError("; ".join(issues))
    topology = ConveyorTopology.from_layout(bundle.layout)
    paths = AllPairsPaths.from_graph(bundle.layout.picker_graph)
    return {
        "status": "passed",
        "issues": [],
        "summary": {
            "layout_version": bundle.layout.layout_version,
            "picker_nodes": len(paths.node_ids),
            "picker_edges": len(bundle.layout.picker_graph.edges),
            "slots": len(bundle.layout.slots),
            "conveyor_cells": len(topology.cells),
            "actors": len(bundle.actors.actors),
        },
    }


def _execute(args: argparse.Namespace, bundle: ContractBundle) -> dict[str, Any]:
    if args.command == "validate-contracts":
        return _validate_contracts(bundle)
    if args.command == "simulate":
        return simulate(bundle, args.profile, args.horizon_s, args.out, args.assignment)
    result = materialize(args.profile, args.horizon_s, bundle.config)
    write_materialized(result, args.out)
    return {
        "status": "passed",
        "scenario_id": result.scenario.scenario_id,
        "shortened_run": args.horizon_s < 3600,
    }


def main(argv: Sequence[str] | None = None) -> int:
    directory = default_contracts_dir().resolve()
    layout_version: str | None = None
    try:
        args = build_parser().parse_args(argv)
        if args.command == "validate-contracts":
            directory = (args.contracts_dir or directory).resolve()
        else:
            require_empty_output(args.out)
        bundle = load_contract_bundle(directory)
        layout_version = bundle.layout.layout_version
        validate_config_file(directory / "simulation_defaults.json")
        report = _execute(args, bundle)
    except AppError as exc:
        report = error_report(exc)
    except (ContractError, ValueError, SchemaValidationError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    except Exception as exc:
        report = error_report(exc)
    report.update(
        engine_version=ENGINE_VERSION, contracts_dir=str(directory), layout_version=layout_version
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "complete"} else 1


if __name__ == "__main__":
    sys.exit(main())
