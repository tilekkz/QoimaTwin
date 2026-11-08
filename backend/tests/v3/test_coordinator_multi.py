"""Hand clocks recorded before the multi-station coordinator implementation."""

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


@pytest.mark.parametrize(
    "candidate,shipments,resource",
    [
        (False, (288_254_551, 319_254_551), 324_254_551),
        (True, (270_170_000, 301_170_000), 306_170_000),
    ],
)
def test_two_stations_share_one_actual_cart_and_shipper(
    candidate: bool,
    shipments: tuple[int, int],
    resource: int,
) -> None:
    result = CoordinatorEngine(multi_profile(candidate=candidate), receipt_conveyor()).run(
        300 * SECOND, 400 * SECOND
    )
    assert result.status == "complete" and result.staffing_status == "valid"
    assert tuple(o.shipped_tick for o in result.at_end.orders) == shipments
    assert result.resource_drained_tick == resource
    assert dict(result.at_horizon.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 6}
    assert {p.station_id for p in result.at_end.packing} == {"PK05", "PK06"}
    assert {p.actor_id for p in result.at_end.packing} == (
        {"P11", "P12"} if candidate else {"K05", "K06"}
    )
    assert len(result.at_end.carts) == 1 and len(result.at_end.workers) == 24


def test_two_real_carts_have_independent_paid_operations_and_same_source_claims() -> None:
    result = CoordinatorEngine(
        multi_profile(candidate=False, two_carts=True), receipt_conveyor()
    ).run(84 * SECOND, 84 * SECOND)
    snap = result.at_end
    assert len(snap.carts) == 2
    assert {c.order_id for c in snap.carts} == {"O1", "O2"}
    assert {c.operation.order_id for c in snap.carts if c.operation} == {"O1", "O2"}
    assert {w.actor_id for w in snap.workers if w.operation} == {"P01", "P02"}
    assert len(snap.inventory.claims) == 2
    assert dict(snap.balance.units_by_sku) == {"SKU1": 24}
