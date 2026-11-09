"""Separately identified storage report after full validation of native coordinator evidence."""

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.coordinator_run import _validate_native
from app.v3.interface import Json
from app.v3.native_read_context import _NativeReadContext
from app.v3.storage_fullness import coordinator_storage_fullness
from app.v3.storage_fullness_models import FULLNESS_VERSION


def build_fullness_report(run: Json, *, inputs: bytes) -> Json:
    return _fullness_from_context(_validate_native(run, inputs=inputs))


def _fullness_from_context(context: _NativeReadContext) -> Json:
    frozen, outcome, run = context.inputs, context.outcome, context.run()
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
