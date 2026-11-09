"""Two actual carriers share one cart, source HU and finite station during helper work."""

from collections import Counter
from dataclasses import replace
from fractions import Fraction as F

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from tests.v3.test_coordinator_packing import packing_profile
from tests.v3.test_light_flow_fixtures import hand_orders, hand_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def two_orders() -> CoordinatorProfile:
    profile = packing_profile(candidate=True)
    flow, materials = profile.world.receipts.flow, hand_profile(orders=2)
    capacities = {o.owner_id: o.capacity for o in materials.owners}
    owners = tuple(replace(o, capacity=capacities.get(o.owner_id, o.capacity)) for o in flow.owners)
    owners += tuple(o for o in materials.owners if o.owner_id not in {v.owner_id for v in owners})
    flow = replace(
        flow,
        materials=materials.materials,
        owners=owners,
        orders=tuple(replace(o, arrival_tick=100 * SECOND) for o in hand_orders(2)),
    )
    return replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )


def test_real_second_carrier_does_not_acquire_first_order_station_or_materials() -> None:
    engine = CoordinatorEngine(two_orders(), receipt_conveyor())
    result = engine.run(145 * SECOND, 145 * SECOND)
    state = result.at_end
    assert result.status == "partial" and result.business_complete_tick is None
    assert Counter(row.container_id for row in state.stock.locations) == {
        "HU1": 18,
        "C1": 3,
        "C2": 3,
    }
    assert len({row.unit_id for row in state.stock.locations}) == 24
    assert state.balance.gross_mass_kg == F("1.44")
    assert not state.balance.shipped_units_by_sku
    containers = {row.container_id: row for row in state.stock.containers}
    assert containers["C1"].owner_id == "belt:O1"
    assert containers["C2"].owner_id == "belt:O2"
    assert containers["P1"].owner_id == "bench"
    assert containers["P2"].owner_id == "package-pool"
    assert [(p.order_id, p.actor_id, p.phase) for p in state.packing] == [("O1", "P12", "pack")]
    assert {c.cart_id for c in state.unit_contexts} == {"CART01"}
    assert {c.job_id for c in state.belt.carriers} == {"O1", "O2"}
    reservation = engine.packing_states["O1"].belt_resources
    assert reservation and all(engine.belt.external[key] == "O1" for key in reservation)
    assert all(engine.belt.leases.get(key) != "O2" for key in reservation)
    assert len(state.workers) == 24
