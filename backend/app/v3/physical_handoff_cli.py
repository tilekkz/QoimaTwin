"""Publish only a reference-validation report; never execute upstream code."""

import argparse
import sys
from pathlib import Path

from app.errors import error_report
from app.storage.canonical_json import canonical_bytes
from app.v3.offer_planning_cli_storage import put, reject_links
from app.v3.physical_handoff_models import VALIDATION_SCOPE, VERSION, PhysicalHandoff
from app.v3.physical_handoff_source import load_physical_handoff


def _claim(assets_root: Path, out: Path) -> None:
    reject_links(assets_root)
    reject_links(out)
    source, target = assets_root.resolve(), out.resolve()
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError("Physical handoff output must not overlap input tree")
    out.mkdir(parents=True, exist_ok=False)


def validate_to_directory(assets_root: Path, out: Path) -> PhysicalHandoff:
    """Claim once before loading; retain failures without overwriting an existing attempt."""
    _claim(assets_root, out)
    try:
        handoff = load_physical_handoff(assets_root)
        report = put(out, "report.json", handoff.frozen_bytes)
        manifest = {
            "version": VERSION,
            "validation_scope": VALIDATION_SCOPE,
            "input_hash": handoff.input_hash,
            "artifacts": [report],
            "operational_admission": False,
            "engine_operation": False,
        }
        put(out, "manifest.json", canonical_bytes(manifest))
        return handoff
    except Exception as exc:
        put(out, "failure.json", canonical_bytes(error_report(exc)))
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--assets-root", type=Path, required=True)
    validate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        validate_to_directory(args.assets_root, args.out)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
