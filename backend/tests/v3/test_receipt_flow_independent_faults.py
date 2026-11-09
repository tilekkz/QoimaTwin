"""Settled shared-world faults must fail before the next stock mutation."""

from dataclasses import replace

import pytest

from app.v3.light_flow_models import FlowSnapshot
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.stock_models import StockOwner
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


@pytest.mark.parametrize("fault", ["pick_claim", "carrying_observation", "unperformed_stock_move"])
def test_shared_receipt_world_detects_lost_claim_or_unperformed_motion(fault: str) -> None:
    inspected = False
    target = 23 * SECOND if fault == "pick_claim" else 12 * SECOND

    def inspect(snapshot: FlowSnapshot, _seq: int) -> None:
        nonlocal inspected
        if snapshot.tick != target:
            return
        inspected = True
        engine._check()
        if fault == "pick_claim":
            assert engine.ledger.claims[0].claim_id == "pick:O1"
            engine.ledger.release_claim("pick:O1", "O1")
        elif fault == "carrying_observation":
            worker = engine.workers["R01"]
            assert worker.operation is not None and worker.operation.carrying_id == "HU2"
            worker.operation = replace(worker.operation, carrying_id=None)
        else:
            assert engine.ledger.contents("HU1").container.owner_id == "slot"
            engine.ledger.transfer_whole_hu(
                "unperformed-source-move", engine.ledger.revision, "HU1", "unvisited-slot"
            )
        with pytest.raises(RuntimeError):
            engine._check()
        raise StopIteration("review stops before advancing the corrupted world")

    profile = receipt_hand_profile()
    owners = (*profile.flow.owners, StockOwner("unvisited-slot", "slot", 1))
    profile = replace(profile, flow=replace(profile.flow, owners=owners))
    engine = ReceiptFlowEngine(profile, receipt_conveyor(), on_tick_settled=inspect)
    with pytest.raises(StopIteration, match="review stops"):
        engine.run(100 * SECOND, 300 * SECOND)
    assert inspected
