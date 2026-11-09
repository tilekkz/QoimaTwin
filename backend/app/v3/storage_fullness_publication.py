"""Separately identified storage report after full validation of native coordinator evidence."""

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.coordinator_run import validate_coordinator_run
from app.v3.coordinator_run_inputs import load_run_inputs
from app.v3.coordinator_run_projection import restore_outcome
from app.v3.interface import Json
from app.v3.storage_fullness import coordinator_storage_fullness
from app.v3.storage_fullness_models import FULLNESS_VERSION


def build_fullness_report(run: Json, *, inputs: bytes) -> Json:
    validate_coordinator_run(run, inputs=inputs)
    frozen = load_run_inputs(inputs)
    outcome = restore_outcome(frozen.profile, run["outcome"])
    result = {
        "version": FULLNESS_VERSION,
        "source_run_id": run["run_id"],
        "input_hash": frozen.input_hash,
        "native_run_sha256": sha256_hex(run),
        "operational_admission": False,
        "at_horizon": coordinator_storage_fullness(frozen.profile, outcome, outcome.at_horizon),
        "at_end": coordinator_storage_fullness(frozen.profile, outcome, outcome.at_end),
    }
    return {**result, "report_id": sha256_hex(result)}


def validate_fullness_report(report: Json, run: Json, *, inputs: bytes) -> None:
    expected = build_fullness_report(run, inputs=inputs)
    if canonical_bytes(report) != canonical_bytes(expected):
        raise ValueError("Storage fullness report differs from verified native observations")
