"""Explicit commands for the isolated V3 source proposal."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.cli import JsonArgumentParser
from app.errors import AppError, InvalidInputError, error_report, require_empty_output
from app.v3.export import write_static_export
from app.v3.inputs import V3Bundle, load_v3_bundle
from app.v3.settings import default_inputs


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="qoima v3", description="V3 proposal tools")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "catalog"):
        command = commands.add_parser(name)
        command.add_argument("--inputs", type=Path, default=default_inputs())
        if name == "catalog":
            command.add_argument("--out", type=Path, required=True)
    return parser


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
        if args.command == "catalog":
            require_empty_output(args.out)
        bundle = load_v3_bundle(args.inputs)
        report = _summary(bundle)
        if args.command == "catalog":
            report["export_id"] = write_static_export(bundle, args.out)["export_id"]
    except AppError as exc:
        report = error_report(exc)
    except (OSError, ValueError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    report.update(layout_version="qoima-144x72-v3-proposal", operational_admission=False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1
