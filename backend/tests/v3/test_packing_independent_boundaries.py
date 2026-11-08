"""Hand pack/clear transaction boundaries keep actual custody separate from future work."""

from collections import Counter
from fractions import Fraction as F

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorSnapshot
from tests.v3.test_coordinator_packing import packing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor

PACK_START = 143_915_448
PACK_END = PACK_START + 3 * SECOND
CLEAR_END = PACK_END + SECOND


def assert_stock(snapshot: CoordinatorSnapshot, *, packed: bool, cleared: bool) -> None:
    counts = Counter(item.container_id for item in snapshot.stock.locations)
    assert counts == {"HU1": 21, "P1" if packed else "C1": 3}
    containers = {item.container_id: item for item in snapshot.stock.containers}
    assert containers["C1"].owner_id == ("empties" if cleared else "belt:O1")
    assert containers["P1"].owner_id == ("belt:O1" if cleared else "bench")
    assert containers["P1"].sealed_for == ("O1" if packed else None)
    assert dict(snapshot.balance.units_by_sku) == {"SKU1": 24}
    assert not snapshot.balance.shipped_units_by_sku
    assert snapshot.balance.gross_mass_kg == F("1.19")


@pytest.mark.parametrize("cap", [PACK_END - 1, PACK_END, CLEAR_END])
def test_cap_preserves_exact_pack_commit_and_separate_clear_handoff(cap: int) -> None:
    engine = CoordinatorEngine(packing_profile(candidate=True), receipt_conveyor())
    result = engine.run(145 * SECOND, cap)
    assert result.status == "partial" and result.business_complete_tick is None
    assert result.resource_drained_tick is None and result.observation_end_tick == cap
    assert_stock(result.at_horizon, packed=False, cleared=False)
    assert_stock(result.at_end, packed=cap >= PACK_END, cleared=cap >= CLEAR_END)
    packing = result.at_end.packing[0]
    assert packing.packed_tick == (PACK_END if cap >= PACK_END else None)
    assert packing.cleared_tick == (CLEAR_END if cap >= CLEAR_END else None)
    assert packing.released_tick == (CLEAR_END if cap >= CLEAR_END else None)
    helper = next(w for w in result.at_end.workers if w.actor_id == "P12")
    role = next(r for r in result.at_end.roles if r.actor_id == "P12")
    assert role.status == "active" and role.return_started_tick is role.restored_tick is None
    assert helper.node == engine.profile.station.node
    if cap < CLEAR_END:
        assert helper.order_id == "O1" and helper.operation is not None
        assert helper.operation.kind == ("pack" if cap < PACK_END else "clear")
        assert helper.operation.planned_end_tick == (PACK_END if cap < PACK_END else CLEAR_END)
        assert engine.belt.external and packing.held_resources
    else:
        assert helper.order_id is None and helper.operation is None
        assert not engine.belt.external and not packing.held_resources
    carrier = result.at_end.belt.carriers[0]
    assert carrier.hu_id == carrier.payload_id == ("P1" if cap >= CLEAR_END else "C1")
    assert len(result.at_end.workers) == 24 and all(e.tick <= cap for e in result.events)
    completed = [
        e.operation.kind
        for e in result.events
        if e.kind == "operation_completed" and e.actor_id == "P12" and e.operation is not None
    ]
    assert ("pack" in completed) is (cap >= PACK_END)
    assert ("clear" in completed) is (cap >= CLEAR_END)
