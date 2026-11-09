"""Multiple cart/claim state and captured equality are distinct from timing oracles."""

import pytest

from app.v3.coordinator_seek import replay_coordinator
from tests.v3.test_coordinator_seek_fixtures import fresh_run
from tests.v3.test_receipt_flow_fixtures import SECOND


def test_two_carts_and_pending_picks_survive_mid_operation_seek() -> None:
    inputs, run, _ = fresh_run("two_carts")
    pending = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=84 * SECOND)
    assert {c.cart_id for c in pending.carts} == {"CART01", "CART02"}
    assert {c.order_id for c in pending.carts} == {"O1", "O2"}
    assert {c.claim_id for c in pending.inventory.claims} == {"pick:O1", "pick:O2"}
    assert pending.cart == next(c for c in pending.carts if c.cart_id == "CART01")
    picked = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=86 * SECOND)
    assert picked.inventory.claims == ()
    for order in inputs.profile.world.receipts.flow.orders:
        assert sum(p.container_id == order.carrier_id for p in picked.stock.locations) == 3
    assert all(p.picked_tick == 86 * SECOND for p in picked.unit_progress)


@pytest.mark.parametrize("kind", ["roles", "receipt", "whole", "two_carts"])
def test_every_captured_tick_matches_native_original_without_snapshot_bootstrap(kind: str) -> None:
    inputs, run, outcome = fresh_run(kind)
    captures = {s.tick: s for s in (*outcome.checkpoints, outcome.at_horizon, outcome.at_end)}
    for tick in sorted(captures, reverse=True):
        assert replay_coordinator(run, inputs=inputs.frozen_bytes, tick=tick) == captures[tick]
