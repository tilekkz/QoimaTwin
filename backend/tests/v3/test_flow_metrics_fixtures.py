"""Independent observation arithmetic; no simulation output supplies expectations."""

from dataclasses import replace

from app.v3.belt_models import BeltSnapshot
from app.v3.light_flow_models import (
    FlowCartView,
    FlowOrder,
    FlowOrderView,
    FlowOutcome,
    FlowProfile,
    FlowSnapshot,
    FlowWorker,
)
from app.v3.stock_ledger import StockLedger
from tests.v3.test_light_flow_fixtures import SECOND, hand_profile


def metric_profile() -> FlowProfile:
    profile = hand_profile(orders=2)
    return replace(
        profile, orders=(profile.orders[0], replace(profile.orders[1], arrival_tick=4 * SECOND))
    )


def _ship(ledger: StockLedger, order: FlowOrder, owner: str) -> None:
    ledger.pick(
        order.order_id + ":pick",
        len(ledger.history),
        order.source_hu,
        order.carrier_id,
        order.carrier_placements,
    )
    ledger.pack(
        order.order_id + ":pack",
        len(ledger.history),
        order.carrier_id,
        order.package_id,
        order.package_placements,
        order_id=order.order_id,
    )
    ledger.ship(
        order.order_id + ":ship",
        len(ledger.history),
        order.package_id,
        owner,
    )


def observation(profile: FlowProfile, seconds: int) -> FlowSnapshot:
    ledger = StockLedger(profile.stock, owners=profile.owners, materials=profile.materials)
    views = []
    for order, admitted, shipped in zip(profile.orders, (1, 6), (8, 18), strict=True):
        done = shipped <= seconds
        if done:
            _ship(ledger, order, profile.shipped_owner)
        views.append(
            FlowOrderView(
                order.order_id,
                "shipped" if done else "waiting",
                admitted * SECOND if admitted <= seconds else None,
                shipped * SECOND if done else None,
            )
        )
    factor = 0 if seconds == 0 else 1 if seconds < 18 else 2
    paid, waited = {"P01": 3, "K06": 2, "S01": 1}, {"P01": 2, "K06": 1}
    workers = tuple(
        FlowWorker(
            a.actor_id,
            a.home,
            None,
            None,
            None,
            waited.get(a.actor_id, 0) * factor * SECOND,
            paid.get(a.actor_id, 0) * factor * SECOND,
        )
        for a in profile.actors
    )
    return FlowSnapshot(
        seconds * SECOND,
        ledger.snapshot(),
        ledger.balance(),
        workers,
        tuple(views),
        (),
        BeltSnapshot(seconds * SECOND, 0, 0, (), (), 5 * factor * SECOND),
        -1,
        FlowCartView(profile.cart.cart_id, profile.cart.home, None, None),
    )


def metric_outcome(profile: FlowProfile) -> FlowOutcome:
    return FlowOutcome("complete", (), observation(profile, 10), observation(profile, 20))
