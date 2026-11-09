"""Freeze forecast provenance, then dispatch the existing paid N1 pair exactly once."""

import argparse
import json
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

from app.errors import AppError, InvalidInputError, error_report
from app.storage.canonical_json import canonical_bytes
from app.v3.forecast_relocation_binding import (
    load_forecast_relocation,
    prepare_forecast_relocation,
    verify_forecast_relocation,
)
from app.v3.forecast_relocation_models import (
    VERSION,
    ForecastRelocationChoices,
    ForecastRelocationInputs,
)
from app.v3.offer_planning_cli_storage import descriptor, put, read_regular, reject_links
from app.v3.relocation_pair_execute import execute_relocation_pair


def _claim(out: Path) -> None:
    reject_links(out)
    out.mkdir(parents=True, exist_ok=False)


def _manifest(
    value: ForecastRelocationInputs, status: str, files: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "status": status,
        "input_hash": value.input_hash,
        "decision_hash": value.decision.input_hash,
        "pair_input_hash": value.pair.input_hash,
        "no_op": value.decision.no_op,
        "files": files,
        "full_n1_acceptance": False,
    }


def _failure(value: ForecastRelocationInputs, out: Path, exc: BaseException) -> None:
    failure = {
        "status": "error",
        "input_hash": value.input_hash,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "partial_outputs_preserved": True,
        "full_n1_acceptance": False,
    }
    # Preserve the original exception even when the output device itself failed.
    with suppress(OSError):
        put(out, "failure.json", canonical_bytes(failure))


def prepare_files(
    decision: Path, common: Path, choices: ForecastRelocationChoices, out: Path
) -> dict[str, Any]:
    value = prepare_forecast_relocation(read_regular(decision), read_regular(common), choices)
    _claim(out)
    try:
        files = [put(out, "inputs.json", value.frozen_bytes)]
        files.append(put(out, "baseline.json", value.pair.baseline.frozen_bytes))
        files.append(put(out, "candidate.json", value.pair.candidate.frozen_bytes))
        report = _manifest(value, "prepared", files)
        put(out, "manifest.json", canonical_bytes(report))
        return report
    except BaseException as exc:
        _failure(value, out, exc)
        raise


def compare_forecast_relocation(
    inputs: bytes | ForecastRelocationInputs, out: Path
) -> dict[str, Any]:
    value = (
        verify_forecast_relocation(inputs)
        if isinstance(inputs, ForecastRelocationInputs)
        else load_forecast_relocation(inputs)
    )
    _claim(out)
    try:
        # No executor can run before the immutable outer provenance exists.
        files = [put(out, "inputs.json", value.frozen_bytes)]
        observed = execute_relocation_pair(value.pair, out / "pair")
        raw = read_regular(out / "pair" / "comparison.json")
        if (
            raw != canonical_bytes(observed)
            or observed["pair_input_hash"] != value.pair.input_hash
            or observed["status"] not in {"complete", "partial"}
        ):
            raise ValueError("Executor report differs from the saved bound comparison")
        files.append(descriptor("pair/comparison.json", raw))
        report = _manifest(value, observed["status"], files)
        put(out, "manifest.json", canonical_bytes(report))
        return report
    except BaseException as exc:
        _failure(value, out, exc)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.v3.forecast_relocation_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Bind saved planning and actual common inputs")
    for flag in ("decision", "common-inputs", "out"):
        prepare.add_argument("--" + flag, type=Path, required=True)
    prepare.add_argument("--job-id", required=True)
    prepare.add_argument("--arrival-tick", type=int, required=True)
    compare = commands.add_parser("compare", help="Execute the bound normal N1 pair once")
    for flag in ("inputs", "out"):
        compare.add_argument("--" + flag, type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            value = prepare_files(
                args.decision,
                args.common_inputs,
                ForecastRelocationChoices(args.job_id, args.arrival_tick),
                args.out,
            )
        else:
            value = compare_forecast_relocation(read_regular(args.inputs), args.out)
    except AppError as exc:
        value = error_report(exc)
    except (OSError, ValueError) as exc:
        value = error_report(InvalidInputError(str(exc)))
    except Exception as exc:
        value = error_report(exc)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value["status"] in {"prepared", "complete", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
