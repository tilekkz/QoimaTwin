"""Separately versioned actual receipt inventory publication and captured checkpoints."""

from app.v3.flow_metrics import summary
from app.v3.interface import Json
from app.v3.receipt_flow_models import RECEIPT_FLOW_ENGINE_VERSION, ReceiptFlowOutcome
from app.v3.receipt_run_inputs import ReceiptRunInputs, verify_frozen
from app.v3.receipt_run_journal import same
from app.v3.receipt_run_native import validate_native
from app.v3.receipt_run_schema import PUBLICATION_VERSION, SCHEMA_ID, schema
from app.v3.receipt_run_validation import receipt_counts, run_identity, validate_receipt_run
from app.v3.receipt_run_values import catalog, checkpoint, event

__all__ = ["build_receipt_run", "validate_receipt_run"]


def build_receipt_run(
    inputs: ReceiptRunInputs, outcome: ReceiptFlowOutcome, *, validate: bool = True
) -> Json:
    frozen = verify_frozen(inputs)
    immutable = catalog(inputs.profile, frozen["graph"])
    validate_native(immutable, outcome)
    snapshots = {s.tick: checkpoint(s) for s in outcome.checkpoints}
    for view in (outcome.at_horizon, outcome.at_end):
        projected = checkpoint(view)
        if view.tick in snapshots:
            same(snapshots[view.tick], projected, "Conflicting actual receipt captures")
        snapshots[view.tick] = projected
    value = _metadata(inputs, outcome)
    value.update(
        catalog=immutable,
        events=[event(e) for e in outcome.events],
        checkpoints=[snapshots[t] for t in sorted(snapshots)],
        at_horizon=checkpoint(outcome.at_horizon),
        at_end=checkpoint(outcome.at_end),
    )
    value["receipt_metrics"] = {
        k: receipt_counts(value[k], value["catalog"]) for k in ("at_horizon", "at_end")
    }
    if validate:
        validate_receipt_run(value)
    return value


def _metadata(inputs: ReceiptRunInputs, outcome: ReceiptFlowOutcome) -> Json:
    capabilities = schema()["properties"]["capabilities"]["properties"]
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        "publication_version": PUBLICATION_VERSION,
        "run_id": run_identity(inputs.input_hash),
        "input_hash": inputs.input_hash,
        "engine_version": RECEIPT_FLOW_ENGINE_VERSION,
        "source_revision": inputs.profile.flow.source_revision,
        "horizon_tick": inputs.horizon_tick,
        "end_tick_limit": inputs.end_tick,
        "observed_until_tick": outcome.at_end.tick,
        "status": outcome.status,
        "capabilities": {k: v["const"] for k, v in capabilities.items()},
        "metrics": summary(inputs.profile.flow, outcome),
    }
