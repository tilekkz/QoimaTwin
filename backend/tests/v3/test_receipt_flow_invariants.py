"""Accounting-valid changes cannot bypass the coordinator's actual motion/resource state."""

import pytest

from app.v3.light_flow_models import FlowSnapshot
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


@pytest.mark.parametrize(
    "failure",
    ["slot_lease", "worker_lease", "hu_claim", "early_buffer", "occupied_slot", "occupied_buffer"],
)
def test_receipt_requires_actual_custody_claim_and_staged_resource_owners(failure: str) -> None:
    checked = False

    def at_tick(snapshot: FlowSnapshot, _seq: int) -> None:
        nonlocal checked
        if snapshot.tick != 12 * SECOND:
            return
        checked = True
        if failure == "slot_lease":
            del engine.leases["receipt:place:new-slot"]
        elif failure == "worker_lease":
            del engine.leases["receipt:worker:R01"]
        elif failure == "hu_claim":
            engine.ledger.release_claim("receipt:R1", "R1")
        elif failure.startswith("occupied_"):
            owner = "new-slot" if failure == "occupied_slot" else "receipt-buffer"
            engine.ledger.transfer_whole_hu("unperformed", engine.ledger.revision, "HU1", owner)
        else:
            engine.ledger.transfer_whole_hu(
                "unperformed",
                engine.ledger.revision,
                "HU2",
                "receipt-buffer",
                claim_id="receipt:R1",
            )
        with pytest.raises(RuntimeError, match=r"receipt|Receipt"):
            engine._check()
        raise StopIteration("probe completed before continuing a corrupted world")

    engine = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor(), on_tick_settled=at_tick)
    with pytest.raises(StopIteration, match="probe completed"):
        engine.run(100 * SECOND, 300 * SECOND)
    assert checked
