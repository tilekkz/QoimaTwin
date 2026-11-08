"""Prewritten C inputs; expected clocks come from the separate hand arithmetic plan."""

from dataclasses import replace

from app.v3.coordinator_models import CoordinatorProfile
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_hand_profile


def separated_arrivals(*, two_shippers: bool = False, receipt: bool = False) -> CoordinatorProfile:
    profile = multi_profile(two_carts=True)
    resources = profile.unit_resources
    assert resources is not None
    flow = profile.world.receipts.flow
    flow = replace(flow, orders=(flow.orders[0], replace(flow.orders[1], arrival_tick=98 * SECOND)))
    if two_shippers:
        resources = replace(
            resources,
            assignments=(
                resources.assignments[0],
                replace(resources.assignments[1], shipper_id="S02"),
            ),
        )
    receipts = profile.world.receipts
    if receipt:
        receipts = receipt_hand_profile(arrival_tick=120 * SECOND)
    return replace(
        profile,
        unit_resources=resources,
        world=replace(profile.world, receipts=replace(receipts, flow=flow)),
    )
