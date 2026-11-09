"""Independent partial-cap facts when distinct actors complete identically named work."""

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.light_flow_models import FlowEvent
from tests.v3.test_coordinator_completion_actor import overlapping_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor

# Independent source edge arithmetic: ceil each edge length/.55 plus turn dwell.
# PK06 prefix/suffix =30_915_448/116_254_552 ticks; full_route follows PK06 first.
# Hand deposit13s, packer approach2s, pack3s, clear1s, packer return2s.
PACKER_HOME = 13 * SECOND + 30_915_448 + (2 + 3 + 1 + 2) * SECOND
OUTPUT = 13 * SECOND + 30_915_448 + (2 + 3 + 1) * SECOND + 116_254_552
# Shipper empty approach2s, pickup1s, loaded3s, service20s; return3+2s.
SHIPPED = OUTPUT + (2 + 1 + 3 + 20) * SECOND
SHIPPER_HOME = SHIPPED + (3 + 2) * SECOND


@pytest.mark.parametrize(
    "cap,foreign_actor,foreign_return_tick",
    [
        (52 * SECOND, "K06", PACKER_HOME),
        (220 * SECOND, "S01", SHIPPER_HOME),
    ],
)
def test_another_actors_return_keeps_picker_return_open(
    cap: int,
    foreign_actor: str,
    foreign_return_tick: int,
) -> None:
    engine = CoordinatorEngine(overlapping_profile(zero_approach=False), receipt_conveyor())
    result = engine.run(SECOND, cap)
    progress = engine.unit_states["O2"]
    assert result.status == "partial"
    assert progress.completed_picker_steps == 10
    assert progress.cart_released_tick is progress.picker_returned_tick is None
    assert engine.leases["cart:CART01"] == "O2"
    picker = next(w for w in result.at_end.workers if w.actor_id == "P01")
    assert picker.operation is not None and picker.operation.kind == "return"
    assert (picker.operation.start_tick, picker.operation.planned_end_tick) == (
        15 * SECOND,
        517 * SECOND,
    )
    foreign_return = [
        e
        for e in result.events
        if e.actor_id == foreign_actor
        and e.kind == "operation_completed"
        and e.operation is not None
        and e.operation.kind == "return"
    ]
    assert len(foreign_return) == 1 and foreign_return[0].tick == foreign_return_tick
    assert not any(
        e.actor_id == "P01"
        and e.kind == "operation_completed"
        and e.tick >= 15 * SECOND
        and e.operation is not None
        and e.operation.kind == "return"
        for e in result.events
    )
    if foreign_actor == "S01":
        assert progress.completed_shipper_steps == 5
        assert progress.shipper_returned_tick == SHIPPER_HOME
        assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
        _shipping_order(result.events)


def _shipping_order(events: tuple[FlowEvent, ...]) -> None:
    completed = next(
        e
        for e in events
        if e.actor_id == "S01"
        and e.kind == "operation_completed"
        and e.operation is not None
        and e.operation.kind == "shipping_service"
    )
    shipped = next(e for e in events if e.kind == "shipped")
    committed = next(e for e in events if e.kind == "parcel_capacity_committed")
    returning = next(
        e
        for e in events
        if e.actor_id == "S01"
        and e.kind == "operation_started"
        and e.operation is not None
        and e.operation.kind == "return"
    )
    assert completed.seq < shipped.seq < committed.seq < returning.seq
    assert {e.tick for e in (completed, shipped, committed, returning)} == {SHIPPED}
    assert shipped.delta is not None and committed.actor_id == "S01"
