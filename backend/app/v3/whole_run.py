"""Native bounded mixed unit/receipt/whole publication, independent of frontend contracts."""

from app.v3.interface import Json
from app.v3.receipt_run_journal import same
from app.v3.receipt_run_native import validate_native
from app.v3.whole_flow_models import WHOLE_FLOW_ENGINE_VERSION, WholeFlowOutcome
from app.v3.whole_run_inputs import WholeRunInputs, verify_inputs
from app.v3.whole_run_metrics import summary
from app.v3.whole_run_schema import PUBLICATION_VERSION, SCHEMA_ID, schema
from app.v3.whole_run_validation import run_identity, validate_whole_run
from app.v3.whole_run_values import catalog, checkpoint, event

__all__ = ["build_whole_run", "validate_whole_run"]


def build_whole_run(
    inputs: WholeRunInputs, outcome: WholeFlowOutcome, *, validate: bool = True
) -> Json:
    if type(outcome) is not WholeFlowOutcome:
        raise ValueError("Whole publication requires its actual native outcome")
    physical = verify_inputs(inputs)
    immutable = catalog(physical)
    validate_native(immutable, outcome)
    snapshots = {s.tick: checkpoint(s) for s in outcome.checkpoints}
    for native in (outcome.at_horizon, outcome.at_end):
        point = checkpoint(native)
        if native.tick in snapshots:
            same(snapshots[native.tick], point, "Conflicting actual whole captures")
        snapshots[native.tick] = point
    value = _metadata(inputs, outcome)
    value.update(
        catalog=immutable,
        events=[event(e) for e in outcome.events],
        checkpoints=[snapshots[t] for t in sorted(snapshots)],
        at_horizon=checkpoint(outcome.at_horizon),
        at_end=checkpoint(outcome.at_end),
    )
    value["metrics"] = summary(value)
    if validate:
        validate_whole_run(value)
    return value


def _metadata(inputs: WholeRunInputs, outcome: WholeFlowOutcome) -> Json:
    capabilities = schema()["properties"]["capabilities"]["properties"]
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        "publication_version": PUBLICATION_VERSION,
        "run_id": run_identity(inputs.input_hash),
        "input_hash": inputs.input_hash,
        "physical_input_hash": inputs.physical_input_hash,
        "engine_version": WHOLE_FLOW_ENGINE_VERSION,
        "source_revision": inputs.profile.receipts.flow.source_revision,
        "horizon_tick": inputs.horizon_tick,
        "end_tick_limit": inputs.end_tick,
        "observed_until_tick": outcome.at_end.tick,
        "status": outcome.status,
        "capabilities": {k: v["const"] for k, v in capabilities.items()},
    }
