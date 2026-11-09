"""One-microsecond source deadline contrast derived from paid approach and service."""

from dataclasses import replace

import pytest

from app.v3.receipt_flow_engine import ReceiptFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


@pytest.mark.parametrize("late_by", [0, 1])
def test_arrival_plus_paid_approach_must_fit_source_window_before_credit(late_by: int) -> None:
    profile = receipt_hand_profile(arrival_tick=3 * SECOND + late_by)
    port = replace(profile.ports[0], windows=((5 * SECOND, 15 * SECOND),))
    profile = replace(profile, ports=(port,), flow=replace(profile.flow, orders=()))
    result = ReceiptFlowEngine(profile, receipt_conveyor()).run(100 * SECOND, 100 * SECOND)
    receipt = result.at_end.receipts[0]
    if late_by:
        assert receipt.admitted_tick is None and receipt.credited_tick is None
        assert not result.at_end.inventory.registered_receipts
        assert len(result.at_end.inventory.locations) == 24
        assert all(w.paid_ticks == 0 for w in result.at_end.workers)
        assert result.status == "partial"
    else:
        assert (receipt.admitted_tick, receipt.credited_tick, receipt.returned_tick) == (
            3 * SECOND,
            15 * SECOND,
            36 * SECOND,
        )
        assert result.at_end.tick == 36 * SECOND and result.status == "complete"
        assert len(result.at_end.inventory.locations) == 48
        assert sum(w.paid_ticks for w in result.at_end.workers) == 33 * SECOND
