"""Strict N1 publication binds the complete plan and common world to recorded physical facts."""

from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_run_inputs import load_run_inputs as load_common
from app.v3.coordinator_run_projection import project_outcome as project_common
from app.v3.coordinator_run_projection import restore_outcome as restore_common
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.relocation_metrics import summary
from app.v3.relocation_models import RELOCATION_VERSION, BoundRelocation
from app.v3.relocation_native_projection import project_outcome, restore_outcome
from app.v3.relocation_run_identity import run_identity
from app.v3.relocation_run_inputs import load_run_inputs, verify_inputs
from app.v3.relocation_run_schema import PUBLICATION_VERSION, envelope
from app.v3.relocation_run_validation import validate_relocation_outcome


def build_relocation_run(inputs: BoundRelocation, outcome: CoordinatorOutcome) -> dict[str, Any]:
    profile = verify_inputs(inputs)
    common = load_common(inputs.common_inputs)
    kind = "relocation" if profile.jobs else "base_noop"
    project = project_outcome if profile.jobs else project_common
    projected = project(profile.coordinator, outcome)
    _, conveyor, _ = _pinned_reference()
    validate_relocation_outcome(profile, conveyor, outcome, common.horizon_tick, common.end_tick)
    return {
        "schema_version": PUBLICATION_VERSION,
        "engine_version": RELOCATION_VERSION,
        "run_id": run_identity(inputs.input_hash),
        "input_hash": inputs.input_hash,
        "common_input_hash": common.input_hash,
        "registry_common_hash": common.registry_common_hash,
        "horizon_tick": common.horizon_tick,
        "end_tick_limit": common.end_tick,
        "observed_until_tick": outcome.at_end.tick,
        "status": outcome.status,
        "metrics": summary(profile, outcome),
        "outcome_kind": kind,
        "outcome": projected,
    }


def validate_relocation_run(run: dict[str, Any], *, inputs: bytes) -> None:
    value = envelope(run)
    frozen = load_run_inputs(inputs)
    kind = "relocation" if frozen.profile.jobs else "base_noop"
    if value["outcome_kind"] != kind:
        raise ValueError("Relocation outcome kind differs from its frozen plan")
    restore = restore_outcome if frozen.profile.jobs else restore_common
    outcome = restore(frozen.profile.coordinator, value["outcome"])
    expected = build_relocation_run(frozen, outcome)
    if canonical_bytes(value) != canonical_bytes(expected):
        raise ValueError("Relocation run metadata, metrics or native identity differs")
