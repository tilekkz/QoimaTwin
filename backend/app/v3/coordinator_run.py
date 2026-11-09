"""Native multi-resource coordinator publication, separate from single-cart whole runs."""

from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_metrics import summary
from app.v3.coordinator_models import COORDINATOR_VERSION, CoordinatorOutcome, CoordinatorProfile
from app.v3.coordinator_run_identity import run_identity
from app.v3.coordinator_run_inputs import RunInputs, load_run_inputs, verify_inputs
from app.v3.coordinator_run_projection import project_outcome, restore_outcome
from app.v3.coordinator_run_schema import PUBLICATION_VERSION, envelope
from app.v3.coordinator_run_validation import validate_outcome
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.native_read_context import _NativeReadContext


def build_coordinator_run(inputs: RunInputs, outcome: CoordinatorOutcome) -> dict[str, Any]:
    profile = verify_inputs(inputs)
    return _build_native(profile, inputs, outcome)


def _build_native(
    profile: CoordinatorProfile, inputs: RunInputs, outcome: CoordinatorOutcome
) -> dict[str, Any]:
    projected = project_outcome(profile, outcome)
    _, source, _ = _pinned_reference()
    validate_outcome(profile, source, outcome, inputs.horizon_tick, inputs.end_tick)
    return {
        "schema_version": PUBLICATION_VERSION,
        "engine_version": COORDINATOR_VERSION,
        "run_id": run_identity(inputs.input_hash),
        "input_hash": inputs.input_hash,
        "registry_common_hash": inputs.registry_common_hash,
        "horizon_tick": inputs.horizon_tick,
        "end_tick_limit": inputs.end_tick,
        "observed_until_tick": outcome.at_end.tick,
        "status": outcome.status,
        "metrics": summary(profile, outcome),
        "outcome": projected,
    }


def validate_coordinator_run(run: dict[str, Any], *, inputs: bytes) -> None:
    _validate_native(run, inputs=inputs)


def _validate_native(run: dict[str, Any], *, inputs: bytes) -> _NativeReadContext:
    value = envelope(run)
    raw = canonical_bytes(value)
    frozen = load_run_inputs(inputs)
    # Decode the original objects: JSON normalization must not erase exact-type aliases.
    outcome = restore_outcome(frozen.profile, value["outcome"])
    expected = _build_native(frozen.profile, frozen, outcome)
    if raw != canonical_bytes(expected):
        raise ValueError("Coordinator run metadata, metrics or native identity differs")
    return _NativeReadContext(raw, frozen, outcome)
