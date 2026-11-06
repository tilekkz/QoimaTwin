"""Command-line entry point: `uv run python -m app.cli <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.contracts.loader import ContractError, load_contract_bundle
from app.contracts.validation import validate_bundle
from app.conveyor.topology import ConveyorTopology, TopologyError
from app.data.scenario_materializer import Profile, materialize, write_materialized
from app.navigation.shortest_paths import AllPairsPaths
from app.settings import default_contracts_dir
from app.version import ENGINE_VERSION


def _validate_contracts(contracts_dir: Path) -> int:
    report: dict[str, object] = {
        "engine_version": ENGINE_VERSION,
        "contracts_dir": str(contracts_dir),
    }
    try:
        bundle = load_contract_bundle(contracts_dir)
        issues = validate_bundle(bundle)
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-contracts":
        return _validate_contracts(args.contracts_dir or default_contracts_dir())
    if args.command == "materialize":
        return _materialize(args.profile, args.horizon_s, args.out)
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":
    sys.exit(main())
