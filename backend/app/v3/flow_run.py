"""Actual connected SMALL trace and fixed captured checkpoints; no arbitrary seek claim."""

from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.flow_metrics import summary
from app.v3.flow_profile import CompiledLightProfile
from app.v3.flow_profile_wire import materialized_record
from app.v3.flow_run_schema import SCHEMA_ID, capability_schema
from app.v3.flow_run_validation import run_identity, validate_flow_run
from app.v3.flow_run_values import catalog, checkpoint, event
from app.v3.light_flow_models import LIGHT_FLOW_ENGINE_VERSION, FlowOutcome
from app.v3.stock_ledger import StockLedger

__all__ = ["build_flow_run", "validate_flow_run"]


def frozen_inputs(inputs: CompiledLightProfile) -> dict[str, Any]:
    value = parse_json(inputs.frozen_bytes)
    if not isinstance(value, dict) or sha256(inputs.frozen_bytes).hexdigest() != inputs.input_hash:
        raise ValueError("Compiled input hash mismatch")
    profile = inputs.profile
    ledger = StockLedger(profile.stock, owners=profile.owners, materials=profile.materials)
    expected = materialized_record(profile, ledger)
    if canonical_bytes({k: value.get(k) for k in expected}) != canonical_bytes(expected):
        raise ValueError("Compiled profile differs from frozen physical inputs")
    choices = value["choices"]
    clocks = {"horizon_tick": inputs.horizon_tick, "end_tick": inputs.end_tick}
    if canonical_bytes({k: choices[k] for k in clocks}) != canonical_bytes(clocks):
        raise ValueError("Compiled clock differs from frozen input choices")
    return value


def build_flow_run(
    inputs: CompiledLightProfile, outcome: FlowOutcome, *, validate: bool = True
) -> dict[str, Any]:
    frozen = frozen_inputs(inputs)
    snapshots = {s.tick: checkpoint(s) for s in outcome.checkpoints}
    for view in (outcome.at_horizon, outcome.at_end):
        projected = checkpoint(view)
        if view.tick in snapshots and snapshots[view.tick] != projected:
            raise ValueError("Conflicting captured states at the same tick")
        snapshots[view.tick] = projected
    value = {
        "schema_id": SCHEMA_ID,
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        "run_id": run_identity(inputs.input_hash),
        "input_hash": inputs.input_hash,
        "engine_version": LIGHT_FLOW_ENGINE_VERSION,
        "source_revision": inputs.profile.source_revision,
        "horizon_tick": inputs.horizon_tick,
        "end_tick_limit": inputs.end_tick,
        "observed_until_tick": outcome.at_end.tick,
        "status": outcome.status,
        "capabilities": {k: v["const"] for k, v in capability_schema()["properties"].items()},
        "catalog": catalog(inputs.profile, frozen["graph"]),
        "metrics": summary(inputs.profile, outcome),
        "events": [event(e) for e in outcome.events],
        "checkpoints": [snapshots[t] for t in sorted(snapshots)],
        "at_horizon": checkpoint(outcome.at_horizon),
        "at_end": checkpoint(outcome.at_end),
    }
    if validate:
        validate_flow_run(value)
    return value
