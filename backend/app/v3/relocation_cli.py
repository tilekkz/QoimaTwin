"""Standalone bounded N1 comparison; source execution is always an explicit command."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.errors import AppError, InvalidInputError, error_report
from app.v3.relocation_pair_execute import execute_relocation_pair
from app.v3.relocation_pair_inputs import prepare_relocation_pair
from app.v3.relocation_run_inputs import load_run_inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.v3.relocation_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare", help="Execute one strict bounded N1 comparison")
    for flag in ("baseline", "candidate", "out"):
        compare.add_argument("--" + flag, type=Path, required=True)
    return parser


def _compare(args: argparse.Namespace) -> dict[str, Any]:
    baseline = load_run_inputs(args.baseline.read_bytes())
    candidate = load_run_inputs(args.candidate.read_bytes())
    pair = prepare_relocation_pair(baseline, candidate, scenario="N1")
    report = execute_relocation_pair(pair, args.out)
    return {
        "status": report["status"],
        "comparison_id": report["comparison_id"],
        "pair_input_hash": report["pair_input_hash"],
        "input_family": report["input_family"],
        "no_op": report["no_op"],
        "report": str(args.out / "comparison.json"),
        "net_paid_ticks": {
            key: value["net_paid_ticks"] for key, value in report["windows"].items()
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = _compare(args)
    except AppError as exc:
        value = error_report(exc)
    except (OSError, ValueError) as exc:
        value = error_report(InvalidInputError(str(exc)))
    except Exception as exc:
        value = error_report(exc)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value["status"] in {"complete", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
