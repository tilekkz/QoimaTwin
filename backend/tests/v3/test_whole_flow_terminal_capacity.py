"""A parcel and an intact HU must share one finite destination's promises."""

from dataclasses import replace

import pytest

from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_flow_models import WholeFlowProfile
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def mixed_terminal_profile(capacity: int = 1) -> WholeFlowProfile:
    profile, receipt = whole_hand_profile("SMALL_CARTON"), receipt_hand_profile()
    flow = replace(
        profile.receipts.flow,
        orders=hand_orders(1),
        owners=tuple(
            replace(owner, capacity=capacity) if owner.owner_id == "shipped" else owner
            for owner in profile.receipts.flow.owners
        ),
    )
    return replace(
        profile,
        receipts=replace(receipt, flow=flow),
        orders=(replace(profile.orders[0], hu_id="HU2", arrival_tick=173 * SECOND),),
        places=(
            *profile.places,
            next(place for place in receipt.places if place.owner_id == "new-slot"),
        ),
    )


def test_active_parcel_keeps_last_destination_place_until_and_after_handoff() -> None:
    # Parcel service is 172.17..192.17. S02 approaches/picks/carries/places
    # the received whole HU in 2+1+3+1 seconds, reaching its buffer at 180.
    outcome = WholeFlowEngine(mixed_terminal_profile(), receipt_conveyor()).run(
        181 * SECOND, 220 * SECOND
    )
    worker = next(w for w in outcome.at_horizon.workers if w.actor_id == "S01")
    assert worker.operation is not None and worker.operation.kind == "shipping_service"
    assert (worker.operation.start_tick, worker.operation.planned_end_tick) == (
        172_170_000,
        192_170_000,
    )
    for snapshot in (outcome.at_horizon, outcome.at_end):
        whole = snapshot.whole_orders[0]
        assert whole.buffered_tick == 180 * SECOND
        assert whole.port_reserved_tick is None
        assert whole.shipped_tick is None
        assert whole.wait_reason == "shipped_capacity"
    assert outcome.at_end.orders[0].shipped_tick == 192_170_000
    assert outcome.status == "partial"


def test_two_destination_places_allow_both_named_ports_to_work() -> None:
    outcome = WholeFlowEngine(mixed_terminal_profile(2), receipt_conveyor()).run(
        181 * SECOND, 220 * SECOND
    )
    whole = outcome.at_end.whole_orders[0]
    assert whole.port_reserved_tick == 180 * SECOND
    # Buffer pick1 + carry4 + service25 + paid return5, starting at180.
    assert whole.service_started_tick == 185 * SECOND
    assert whole.shipped_tick == 210 * SECOND
    assert whole.returned_tick == 215 * SECOND
    assert outcome.at_end.orders[0].shipped_tick == 192_170_000
    assert outcome.status == "complete"


class OverbookingEngine(WholeFlowEngine):
    """Model faulty admission while retaining all settled-state invariants."""

    def _has_owner_capacity(self, owner_id: str) -> bool:
        reserved = sum(
            self.whole_ports[state.spec.port_id].shipped_owner == owner_id
            and state.port_reserved_tick is not None
            and state.shipped_tick is None
            for state in self.whole_orders.values()
        )
        occupied = sum(c.owner_id == owner_id for c in self.ledger.snapshot().containers)
        return occupied + reserved < self.owner_specs[owner_id].capacity


def test_settled_invariants_reject_a_second_promise_even_before_stock_moves() -> None:
    engine = OverbookingEngine(mixed_terminal_profile(), receipt_conveyor())
    with pytest.raises(RuntimeError, match="Shipped owner capacity"):
        engine.run(181 * SECOND, 181 * SECOND)
