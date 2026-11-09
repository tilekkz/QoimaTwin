"""New-version dispatch uses effective readiness and explicit source-pool actor ownership."""

from dataclasses import replace

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_light_flow_fixtures import hand_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile
from tests.v3.test_whole_flow_shared_fixtures import standard_receipt_chain


def test_shared_parcel_dispatch_selects_actual_ready_fifo_candidate() -> None:
    """Isolated scheduler-state test, not a physical replay or full engine run."""
    profile = whole_hand_profile("SMALL_CARTON")
    flow = hand_profile(orders=2)
    owners = tuple(
        replace(o, kind="worker") if o.owner_id in {"actor:P01", "actor:S01"} else o
        for o in flow.owners
    )
    flow = replace(flow, owners=owners)
    receipts = replace(profile.receipts, flow=flow)
    engine = WholeFlowEngine(
        replace(profile, receipts=receipts, orders=(), ports=(), places=()), receipt_conveyor()
    )
    for order in engine.orders.values():
        order.status = "output"
    engine.belt.at_output.update({"O1", "O2"})
    engine.parcel_ready.update({"O1": 20 * SECOND, "O2": 10 * SECOND})
    engine.tick = 30 * SECOND
    engine._dispatch_shipment()
    assert engine.workers["S01"].order_id == "O2"


def test_standard_receipt_prospective_validation_uses_declared_r02_not_implicit_r01() -> None:
    profile = standard_receipt_chain()
    flow = profile.receipts.flow
    owners = tuple(
        replace(o, owner_id="actor:R02") if o.owner_id == "actor:R01" else o for o in flow.owners
    )
    actors = tuple(replace(a, home="RH") if a.actor_id == "R02" else a for a in flow.actors)
    receipts = replace(
        profile.receipts,
        flow=replace(flow, owners=owners, actors=actors),
        ports=(replace(profile.receipts.ports[0], receiver_ids=("R02",)),),
    )
    result = WholeFlowEngine(replace(profile, receipts=receipts), receipt_conveyor()).run(
        100 * SECOND, 200 * SECOND
    )
    assert result.at_end.receipts[0].actor_id == "R02"
    assert result.at_end.whole_orders[0].returned_tick == 83 * SECOND
