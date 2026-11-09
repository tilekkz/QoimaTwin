"""Verified data-only N1 reader; arbitrary settled cuts are neither forecasts nor engine saves."""

from hashlib import sha256

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_run_inputs import load_run_inputs as load_common
from app.v3.coordinator_run_projection import restore_outcome as restore_base
from app.v3.coordinator_run_validation import Journal
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.interface import Json
from app.v3.relocation_native_projection import restore_outcome
from app.v3.relocation_replay_state import project_snapshot, reduce
from app.v3.relocation_run import validate_relocation_run
from app.v3.relocation_run_inputs import load_run_inputs
from app.v3.relocation_run_validation import RelocationJournal

READER_VERSION = "qoima-relocation-settled-replay-0.1.0"


def replay_relocation_run(run: Json, *, inputs: bytes, tick: int) -> Json:
    if type(tick) is not int or tick < 0:
        raise ValueError("Relocation replay requires an exact nonnegative integer tick")
    validate_relocation_run(run, inputs=inputs)
    if tick > run["observed_until_tick"]:
        raise ValueError("Relocation replay cannot infer unobserved future state")
    frozen = load_run_inputs(inputs)
    common = load_common(frozen.common_inputs)
    _, source, _ = _pinned_reference()
    journal: Journal
    if frozen.plans:
        outcome = restore_outcome(frozen.profile.coordinator, run["outcome"])
        journal = RelocationJournal(
            frozen.profile, source, outcome, frozen.plans, common.horizon_tick
        )
    else:
        outcome_base = restore_base(frozen.profile.coordinator, run["outcome"])
        journal = Journal(frozen.profile.coordinator, source, outcome_base, common.horizon_tick)
        point = reduce(journal, outcome_base, tick)
        return _frame(run, project_snapshot(frozen.profile.coordinator, point), tick)
    point = reduce(journal, outcome, tick)
    return _frame(run, project_snapshot(frozen.profile.coordinator, point), tick)


def _frame(run: Json, point: Json, tick: int) -> Json:
    return {
        "reader_version": READER_VERSION,
        "reader_capabilities": {
            "arbitrary_settled_state": True,
            "engine_restore": False,
            "geometric_interpolation": False,
            "full_v3": False,
        },
        "scope": "verified_native_settled_state",
        "state_boundary": "after_all_observed_events_with_tick_lte_T",
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "common_input_hash": run["common_input_hash"],
        "registry_common_hash": run["registry_common_hash"],
        "native_outcome_sha256": sha256(canonical_bytes(run["outcome"])).hexdigest(),
        "engine_version": run["engine_version"],
        "publication_version": run["schema_version"],
        "outcome_kind": run["outcome_kind"],
        "tick": tick,
        "last_seq": point["last_seq"],
        "observed_until_tick": run["observed_until_tick"],
        "snapshot": point,
    }
