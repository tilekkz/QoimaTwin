"""Explicit normal CLI for forecast planning and strict saved-bundle validation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from app.cli import JsonArgumentParser
from app.errors import AppError, InvalidInputError, error_report
from app.v3.offer_planning_cli_models import PlanningFiles
from app.v3.offer_planning_cli_pipeline import plan_offer_files
from app.v3.offer_planning_cli_validation import validate_offer_plan

COMMANDS = ("plan-offers", "validate-offer-plan")


def add_commands(commands: argparse._SubParsersAction[JsonArgumentParser]) -> None:
    plan = commands.add_parser("plan-offers", help="plan forecast offers; never execute work")
    for name in ("history", "history-choices", "projection-choices", "placement-choices", "out"):
        plan.add_argument("--" + name, type=Path, required=True)
    plan.add_argument("--model", choices=("mean28", "hgb"), required=True)
    validate = commands.add_parser("validate-offer-plan", help="validate saved planning evidence")
    validate.add_argument("--bundle", type=Path, required=True)


def main(argv: Sequence[str]) -> int:
    try:
        parser = JsonArgumentParser(prog="qoima v3", description="Data-only forecast planning")
        add_commands(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(argv)
        if args.command == "validate-offer-plan":
            report = validate_offer_plan(args.bundle)
        else:
            paths = PlanningFiles(
                args.history, args.history_choices, args.projection_choices, args.placement_choices
            )
            report = plan_offer_files(paths, args.model, args.out)
    except AppError as exc:
        report = error_report(exc)
    except (ValueError, OSError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    except Exception as exc:
        report = error_report(exc)
    report.update(operational_admission=False, actual_test_stream=False, engine_calls=0)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "planned", "no-op", "infeasible"} else 1
