"""Accounting-valid moves still require the actual physical completion and current claims."""

from dataclasses import replace

import pytest

from app.v3.light_flow_models import FlowSnapshot
from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


@pytest.mark.parametrize("fault", ["claim", "carrying", "unperformed_move", "worker", "buffer"])
def test_original_whole_physical_world_rejects_bypasses(fault: str) -> None:
    visited = False

    def inspect(snapshot: FlowSnapshot, _seq: int) -> None:
        nonlocal visited
        if snapshot.tick != 3 * SECOND:
            return
        visited = True
        engine._check()
        if fault == "claim":
            engine.ledger.release_claim("whole:W1", "W1")
        elif fault == "carrying":
            actor = engine.workers["S01"]
            assert actor.operation is not None
            actor.operation = replace(actor.operation, carrying_id=None)
        elif fault == "unperformed_move":
            engine.ledger.transfer_whole_hu(
                "illegal", engine.ledger.revision, "HU1", "whole-buffer", claim_id="whole:W1"
            )
        else:
            del engine.leases[
                "whole:worker:S01" if fault == "worker" else "whole:place:whole-buffer"
            ]
        with pytest.raises(RuntimeError):
            engine._check()
        raise StopIteration("fault stopped")

    engine = WholeFlowEngine(whole_hand_profile(), receipt_conveyor(), on_tick_settled=inspect)
    with pytest.raises(StopIteration, match="fault stopped"):
        engine.run(100 * SECOND, 200 * SECOND)
    assert visited
