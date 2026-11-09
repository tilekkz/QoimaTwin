"""Role offers wait for actual shared-worker custody release, with no forced handoff."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile, RoleIntent
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.staff_registry import compile_staff_registry
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_staff_registry_fixtures import registry_document


def busy_picker_profile() -> CoordinatorProfile:
    profile = staffing_profile()
    flow = profile.world.receipts.flow
    arcs = (
        *flow.graph.arcs,
        *(
            Arc(f"role:{a}:{b}", a, b, F(6), F(6), modes=frozenset({"pedestrian"}))
            for a, b in (("H", "ST05"), ("ST05", "H"))
        ),
    )
    flow = replace(
        flow, graph=DirectedGraph("busy-picker", flow.graph.node_ids, arcs), orders=hand_orders(1)
    )
    document = registry_document()
    document["workers"][0]["eligible_roles"] = ["pick", "pack"]
    document["unavailability"] = [
        {
            "actor_id": "K05",
            "start_tick": 10 * SECOND,
            "end_tick": 100 * SECOND,
            "reason": "declared_break",
        }
    ]
    intent = RoleIntent("I01", "P01", "PK05", 10 * SECOND, 94 * SECOND, 100 * SECOND, "H")
    return replace(
        profile,
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
        registry=compile_staff_registry(document),
        intents=(intent,),
    )


def test_busy_picker_keeps_paid_job_until_actual_cart_and_custody_release() -> None:
    result = CoordinatorEngine(busy_picker_profile(), receipt_conveyor()).run(
        200 * SECOND, 240 * SECOND
    )
    role = result.at_end.roles[0]
    assert (role.departed_tick, role.activated_tick, role.restored_tick) == (
        20 * SECOND,
        26 * SECOND,
        100 * SECOND,
    )
    assert next(w for w in result.at_end.workers if w.actor_id == "P01").paid_ticks == 32 * SECOND
    assert result.at_end.orders[0].shipped_tick == 192_170_000
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert result.staffing_status == "valid" and not result.at_end.leases


def test_occupied_physical_bench_denies_helper_without_moving_its_contents() -> None:
    profile = staffing_profile()
    flow = profile.world.receipts.flow
    materials = tuple(
        replace(c, owner_id="bench05") if c.container_id == "P1" else c for c in flow.materials
    )
    flow = replace(flow, materials=materials)
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(200 * SECOND, 200 * SECOND)
    denied = next(r for r in result.at_end.roles if r.actor_id == "P11")
    assert denied.status == "rejected" and denied.departed_tick is None
    assert (
        next(c for c in result.at_end.stock.containers if c.container_id == "P1").owner_id
        == "bench05"
    )
    assert next(w for w in result.at_end.workers if w.actor_id == "P11").paid_ticks == 0
    assert not result.at_end.leases and result.staffing_status == "violated"


def test_one_second_before_restoration_both_actual_returns_remain_open() -> None:
    result = CoordinatorEngine(staffing_profile(), receipt_conveyor()).run(
        159 * SECOND, 159 * SECOND
    )
    assert result.status == "partial" and result.resource_drained_tick is None
    assert all(r.status == "returning" and r.restored_tick is None for r in result.at_end.roles)
    workers = {w.actor_id: w for w in result.at_end.workers}
    for actor in ("P11", "P12"):
        operation = workers[actor].operation
        assert workers[actor].node is None and operation is not None
        assert operation.planned_end_tick == 160 * SECOND
    assert result.at_end.exposure.transition_ticks == 18 * SECOND


def test_role_and_station_input_permutation_preserves_exact_native_outcome() -> None:
    profile = staffing_profile()
    changed = replace(
        profile,
        intents=tuple(reversed(profile.intents)),
        stations=tuple(reversed(profile.stations)),
    )
    original = CoordinatorEngine(profile, receipt_conveyor()).run(200 * SECOND, 200 * SECOND)
    assert (
        CoordinatorEngine(changed, receipt_conveyor()).run(200 * SECOND, 200 * SECOND) == original
    )
