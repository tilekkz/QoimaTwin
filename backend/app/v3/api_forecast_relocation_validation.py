"""Authenticate the complete existing native pair and its outer forecast provenance."""

import tempfile
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_run_projection import restore_outcome as restore_base
from app.v3.forecast_relocation_cli import _manifest
from app.v3.forecast_relocation_models import ForecastRelocationInputs
from app.v3.offer_planning_cli_storage import descriptor, put, read_regular
from app.v3.relocation_native_projection import restore_outcome as restore_relocation
from app.v3.relocation_pair_report import build_pair_report
from app.v3.relocation_transport import read_relocation_run
from app.v3.relocation_transport_schema import validate_manifest

FIXED = frozenset({"inputs.json", "manifest.json", "pair/inputs.json", "pair/comparison.json"})


def inventory(raw: dict[str, bytes]) -> None:
    expected = set(FIXED)
    for arm in ("baseline", "candidate"):
        prefix = "pair/" + arm + "/"
        expected.add(prefix + "manifest.json")
        refs = validate_manifest(parse_json(raw[prefix + "manifest.json"]))
        for ref in refs:
            name = prefix + ref["path"]
            expected.add(name)
            actual = descriptor(ref["path"], raw[name])
            if canonical_bytes(actual) != canonical_bytes({k: ref[k] for k in actual}):
                raise ValueError("Native pair file differs from its manifest")
    if set(raw) != expected:
        raise ValueError("Forecast relocation requires its complete closed native inventory")


def output_files(root: Path) -> dict[str, bytes]:
    raw = {
        path.relative_to(root).as_posix(): read_regular(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    inventory(raw)
    return raw


def _outcome(value: ForecastRelocationInputs, arm: str, run: dict[str, Any]) -> CoordinatorOutcome:
    profile = getattr(value.pair, arm).profile
    if profile.jobs:
        return restore_relocation(profile.coordinator, run["outcome"])
    return restore_base(profile.coordinator, run["outcome"])


def validate_output(raw: dict[str, bytes], value: ForecastRelocationInputs) -> dict[str, Any]:
    inventory(raw)
    if (
        raw["inputs.json"] != value.frozen_bytes
        or raw["pair/inputs.json"] != value.pair.frozen_bytes
    ):
        raise ValueError("Saved outer/pair inputs differ from freshly bound decision and common")
    for arm in ("baseline", "candidate"):
        if raw["pair/" + arm + "/inputs.json"] != getattr(value.pair, arm).frozen_bytes:
            raise ValueError("Native arm is not the correlated arm of this forecast decision")
    with tempfile.TemporaryDirectory(prefix="qoima-forecast-relocation-read-") as temporary:
        root = Path(temporary)
        for name, data in raw.items():
            put(root, name, data)
        left = read_relocation_run(root / "pair/baseline")
        right = read_relocation_run(root / "pair/candidate")
        report = build_pair_report(
            value.pair,
            left,
            right,
            _outcome(value, "baseline", left),
            _outcome(value, "candidate", right),
        )
    if raw["pair/comparison.json"] != canonical_bytes(report):
        raise ValueError("Saved comparison differs from both authenticated native outcomes")
    files = [
        descriptor("inputs.json", value.frozen_bytes),
        descriptor("pair/comparison.json", raw["pair/comparison.json"]),
    ]
    expected = _manifest(value, report["status"], files)
    if report["status"] not in {"complete", "partial"} or raw["manifest.json"] != canonical_bytes(
        expected
    ):
        raise ValueError("Outer completion manifest differs from the actual native comparison")
    return dict(
        calculation_status="completed",
        comparison_status=report["status"],
        bridge_input_hash=value.input_hash,
        decision_hash=value.decision.input_hash,
        pair_input_hash=value.pair.input_hash,
        comparison_id=report["comparison_id"],
        no_op=value.decision.no_op,
        full_n1_acceptance=False,
        operational_admission=False,
        comparison=report,
    )
