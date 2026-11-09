"""Mixed shared-bay arithmetic is copied from the prior hand oracle, not runtime output."""

from dataclasses import replace

from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_run import build_whole_run
from app.v3.whole_run_inputs import freeze_hand_inputs
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import two_whole_jobs


def test_parcel_and_whole_use_one_port_and_once_counted_common_labor() -> None:
    profile = two_whole_jobs()
    flow = profile.receipts.flow
    flow = replace(
        flow,
        orders=hand_orders(1),
        port=replace(flow.port, port_id="OUT_W_RETAIL", node="WP", service_tick=25 * SECOND),
    )
    profile = replace(
        profile,
        receipts=replace(profile.receipts, flow=flow),
        orders=(replace(profile.orders[1], arrival_tick=180 * SECOND),),
        ports=(replace(profile.ports[0], shipper_ids=("S02",)),),
    )
    conveyor = receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 190 * SECOND, 300 * SECOND)
    outcome = WholeFlowEngine(profile, conveyor).run(inputs.horizon_tick, inputs.end_tick)
    run = build_whole_run(inputs, outcome)
    end = run["metrics"]["at_end"]
    assert (end["unit"]["completed_units"], end["whole"]["completed_units"]) == (3, 24)
    assert run["at_end"]["tick"] == 246_170_000
    row = run["at_end"]["state"]["whole_orders"][0]
    assert row["port_reserved_tick"] == 201_170_000
    assert row["shipped_tick"] == 241_170_000
    assert end["labor"]["assigned_wait_ticks"] >= 14_170_000
    assert len(end["labor"]["actors"]) == 24
