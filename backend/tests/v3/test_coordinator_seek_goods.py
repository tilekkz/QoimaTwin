"""Receipt12/23/33 and whole47/52 business/resource clocks precede implementation."""

from app.v3.coordinator_seek import replay_coordinator
from tests.v3.test_coordinator_seek_fixtures import fresh_run
from tests.v3.test_receipt_flow_fixtures import SECOND


def test_receipt_credit_is_inclusive_and_backward_seek_cannot_leak_future_tokens() -> None:
    inputs, run, _ = fresh_run("receipt")
    before = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=12 * SECOND - 1)
    credited = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=12 * SECOND)
    placed = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=23 * SECOND)
    earlier = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=12 * SECOND - 1)
    assert before == earlier
    assert sum(n for _, n in before.balance.units_by_sku) == 24
    assert sum(n for _, n in credited.balance.units_by_sku) == 48
    assert len(credited.inventory.claims) == 1
    assert placed.inventory.claims == ()
    assert placed.receipts[0].placed_tick == 23 * SECOND
    assert placed.receipts[0].returned_tick is None
    worker = next(w for w in placed.workers if w.actor_id == "R01")
    assert worker.operation is not None and worker.operation.planned_end_tick == 33 * SECOND
    returned = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=33 * SECOND)
    assert returned.receipts[0].returned_tick == 33 * SECOND


def test_whole_ship_handover_releases_port_but_not_paid_shipper_return() -> None:
    inputs, run, _ = fresh_run("whole")
    before = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=47 * SECOND - 1)
    shipped = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=47 * SECOND)
    returning = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=48 * SECOND)
    assert sum(n for _, n in before.balance.shipped_units_by_sku) == 0
    assert sum(n for _, n in shipped.balance.shipped_units_by_sku) == 24
    assert shipped.inventory.claims == ()
    assert shipped.whole_orders[0].shipped_tick == 47 * SECOND
    assert shipped.whole_orders[0].returned_tick is None
    assert not any(key.startswith("port:") for key, _ in returning.leases)
    assert ("whole:worker:S01", "W1") in returning.leases
    worker = next(w for w in returning.workers if w.actor_id == "S01")
    assert worker.operation is not None and worker.operation.planned_end_tick == 52 * SECOND
