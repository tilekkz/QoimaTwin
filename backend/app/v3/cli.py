"""Explicit commands for the isolated V3 source proposal."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.cli import JsonArgumentParser
from app.errors import AppError, InvalidInputError, error_report, require_empty_output
from app.v3.cli_belt import simulate_conveyor
from app.v3.cli_coordinator import simulate_coordinator_file
from app.v3.cli_coordinator_calendar import materialize_coordinator_calendar_file
from app.v3.cli_coordinator_pair import compare_coordinator_files
from app.v3.cli_lightflow import simulate_light_file
from app.v3.cli_manual import materialize_manual, simulate_manual
from app.v3.cli_receipt import simulate_receipt_file
from app.v3.cli_workload import materialize_workload_file
from app.v3.export import write_static_export
from app.v3.inputs import V3Bundle, load_v3_bundle
from app.v3.settings import default_inputs
from app.v3.whole_cli import simulate_whole_file


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="qoima v3", description="V3 proposal tools")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate",
        "catalog",
        "materialize-manual",
        "simulate-manual",
        "simulate-conveyor",
        "simulate-light",
        "simulate-receipt",
        "simulate-whole",
        "simulate-coordinator",
        "materialize-coordinator-calendar",
        "materialize-workload",
        "compare-coordinator",
    ):
        command = commands.add_parser(name)
        command.add_argument("--inputs", type=Path, default=default_inputs())
        if name != "validate":
            command.add_argument("--out", type=Path, required=True)
        if name.endswith("-manual") or name in {
            "simulate-conveyor",
            "simulate-light",
            "simulate-receipt",
            "simulate-whole",
            "simulate-coordinator",
            "materialize-coordinator-calendar",
        }:
            command.add_argument("--profile", type=Path, required=True)
        if name == "materialize-workload":
            command.add_argument("--policy", type=Path, required=True)
        if name == "materialize-coordinator-calendar":
            command.add_argument("--calendar", type=Path, required=True)
        if name == "compare-coordinator":
            _pair_arguments(command)
    return parser


def _pair_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--baseline", type=Path, required=True)
    command.add_argument("--candidate", type=Path, required=True)
    command.add_argument("--scenario", choices=("N0", "N4"), required=True)


def _summary(bundle: V3Bundle) -> dict[str, Any]:
    return {
        "status": "passed",
        "data_kind": bundle.data_kind,
        "source_revision": bundle.source_revision,
        "layout_content_hash": bundle.layout_content_hash,
        "source_files": len(bundle.source_inventory),
        "baseline": asdict(bundle.baseline),
    }


def main(argv: Sequence[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command != "validate":
            require_empty_output(args.out)
        report = _execute(args)
    except AppError as exc:
        report = error_report(exc)
    except (OSError, ValueError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    except RuntimeError as exc:
        report = error_report(exc)
    report.update(layout_version="qoima-144x72-v3-proposal", operational_admission=False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "complete"} else 1


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "compare-coordinator":
        return compare_coordinator_files(
            args.inputs,
            args.baseline,
            args.candidate,
            args.scenario,
            args.out,
        )
    if args.command == "simulate-coordinator":
        return simulate_coordinator_file(args.inputs, args.profile, args.out)
    if args.command == "materialize-coordinator-calendar":
        return materialize_coordinator_calendar_file(
            args.inputs, args.profile, args.calendar, args.out
        )
    if args.command == "simulate-whole":
        return simulate_whole_file(args.inputs, args.profile, args.out)
    if args.command == "simulate-receipt":
        return simulate_receipt_file(args.inputs, args.profile, args.out)
    if args.command == "simulate-light":
        return simulate_light_file(args.inputs, args.profile, args.out)
    if args.command == "materialize-workload":
        return materialize_workload_file(args.inputs, args.policy, args.out)
    if args.command == "simulate-conveyor":
        return simulate_conveyor(args.inputs, args.profile, args.out)
    if args.command == "materialize-manual":
        return materialize_manual(args.inputs, args.profile, args.out)
    if args.command == "simulate-manual":
        return simulate_manual(args.inputs, args.profile, args.out)
    bundle = load_v3_bundle(args.inputs)
    report = _summary(bundle)
    if args.command == "catalog":
        report["export_id"] = write_static_export(bundle, args.out)["export_id"]
    return report
