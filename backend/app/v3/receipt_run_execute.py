"""Publish verified physical inputs before constructing the single shared receipt clock."""

from pathlib import Path

from app.errors import require_empty_output
from app.v3.conveyor_models import ConveyorSource
from app.v3.interface import Json
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_run_inputs import ReceiptRunInputs, verify_conveyor, verify_frozen
from app.v3.receipt_transport import write_receipt_run
from app.v3.run_publication import publish


def simulate_receipt(inputs: ReceiptRunInputs, conveyor: ConveyorSource, out: Path) -> Json:
    require_empty_output(out)
    frozen = verify_frozen(inputs)
    verify_conveyor(frozen, conveyor)
    publish(out, "inputs.json", inputs.frozen_bytes)
    outcome = ReceiptFlowEngine(inputs.profile, conveyor).run(inputs.horizon_tick, inputs.end_tick)
    run = build_receipt_run(inputs, outcome, validate=False)
    manifest = write_receipt_run(run, out, inputs=inputs.frozen_bytes)
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "manifest": str(out / "manifest.json"),
        "metrics": run["metrics"],
        "receipt_metrics": run["receipt_metrics"],
        "capabilities": run["capabilities"],
        "event_chunks": len(manifest["event_chunks"]),
        "checkpoint_chunks": len(manifest["checkpoint_chunks"]),
    }
