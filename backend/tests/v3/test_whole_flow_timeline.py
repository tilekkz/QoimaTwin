"""Independent arithmetic: 2+1+3+1+1+4+service+5, with intact original stock."""

import pytest

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


@pytest.mark.parametrize(
    ("archetype", "ship", "home"), [("SMALL_CARTON", 37, 42), ("STANDARD_CARTON", 47, 52)]
)
def test_whole_original_hu_has_paid_exact_handoffs(archetype: str, ship: int, home: int) -> None:
    profile = whole_hand_profile(archetype)
    engine = WholeFlowEngine(profile, receipt_conveyor())
    outcome = engine.run(100 * SECOND, 200 * SECOND)
    job = outcome.at_end.whole_orders[0]
    assert outcome.status == "complete"
    assert (job.admitted_tick, job.picked_tick, job.buffered_tick) == (0, 3 * SECOND, 7 * SECOND)
    assert (job.shipped_tick, job.returned_tick) == (ship * SECOND, home * SECOND)
    assert outcome.at_end.tick == home * SECOND
    assert len(outcome.at_end.workers) == 24
    assert dict(outcome.at_end.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert not outcome.at_end.inventory.claims and not outcome.at_end.leases
    assert (
        engine.ledger.contents("HU1").container.recipe
        is profile.receipts.flow.stock.containers[0].recipe
    )
    assert not any(e.kind == "picked" for e in outcome.events)


def test_business_handover_at_horizon_keeps_paid_worker_return() -> None:
    outcome = WholeFlowEngine(whole_hand_profile(), receipt_conveyor()).run(
        47 * SECOND, 60 * SECOND
    )
    job = outcome.at_horizon.whole_orders[0]
    assert job.shipped_tick == 47 * SECOND and job.returned_tick is None
    assert dict(outcome.at_horizon.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert next(w for w in outcome.at_horizon.workers if w.actor_id == "S01").order_id == "W1"
    assert outcome.at_end.tick == 52 * SECOND
