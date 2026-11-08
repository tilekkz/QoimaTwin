"""Actual concurrent actor completions must not advance another actor's plan."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units import picking_steps
from app.v3.coordinator_units_runtime import completed
from app.v3.light_flow_state import HumanState
from app.v3.runtime_graph import DirectedGraph
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def overlapping_profile(
    *, zero_approach: bool, return_metres: int = 500, shipper_at_output: bool = False
) -> CoordinatorProfile:
    profile = multi_profile(candidate=False)
    flow, resources = profile.world.receipts.flow, profile.unit_resources
    assert resources is not None
    arcs = tuple(
        replace(a, length_m=F(return_metres), cost_m=F(return_metres))
        if (a.source, a.target) == ("PARK", "SLOT")
        else a
        for a in flow.graph.arcs
    )
    homes = {"K06": "PACK"} if zero_approach else {}
    if shipper_at_output:
        homes["S01"] = "OUT"
    flow = replace(
        flow,
        graph=DirectedGraph("actor-completion-hand", flow.graph.node_ids, arcs),
        actors=tuple(replace(a, home=homes.get(a.actor_id, a.home)) for a in flow.actors),
        orders=(replace(flow.orders[1], arrival_tick=0),),
    )
    return replace(
        profile,
        registry=replace(profile.registry, unavailability=()),
        unit_resources=replace(resources, assignments=(resources.assignments[1],)),
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
    )


@pytest.mark.parametrize("zero_approach", [False, True])
def test_packer_and_shipper_finish_while_picker_is_still_returning(zero_approach: bool) -> None:
    engine = CoordinatorEngine(
        overlapping_profile(zero_approach=zero_approach, shipper_at_output=zero_approach),
        receipt_conveyor(),
    )
    steps = picking_steps(engine._flow_for_order("O2"))
    # Attach1 + loaded2 + pick3 + loaded3 + park1 + detach1 + carry1 + deposit1.
    assert sum(s.duration for s in steps[:8]) == 13 * SECOND
    # Return1 + rejoin1, then directed PARK->SLOT500 + SLOT->H2 at 1m/s.
    assert sum(s.duration for s in steps) == 517 * SECOND
    result = engine.run(300 * SECOND, 600 * SECOND)
    state = engine.unit_states["O2"]
    assert result.status == "complete" and result.staffing_status == "valid"
    assert state.completed_picker_steps == len(state.picker_steps) == 11
    assert state.completed_shipper_steps == len(state.shipper_steps) == 5
    assert state.picked_tick == 6 * SECOND and state.deposited_tick == 13 * SECOND
    assert state.cart_released_tick == state.picker_returned_tick == 517 * SECOND
    assert state.shipper_returned_tick is not None and state.shipper_returned_tick < 300 * SECOND
    picker = next(w for w in result.at_horizon.workers if w.actor_id == "P01")
    assert picker.operation is not None and picker.operation.kind == "return"
    assert (picker.operation.start_tick, picker.operation.planned_end_tick) == (
        15 * SECOND,
        517 * SECOND,
    )
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert not result.at_end.leases
    returns = [
        e
        for e in result.events
        if e.actor_id in {"K06", "S01"}
        and e.kind == "operation_completed"
        and e.operation is not None
        and e.operation.kind == "return"
    ]
    assert returns and all(15 * SECOND < e.tick < 517 * SECOND for e in returns)
    committed = next(
        i for i, e in enumerate(result.events) if e.kind == "parcel_capacity_committed"
    )
    assert result.events[committed - 1].kind == "shipped"
    assert result.events[committed].actor_id == "S01"


def test_short_return_control_preserves_completed_steps() -> None:
    engine = CoordinatorEngine(
        overlapping_profile(zero_approach=False, return_metres=3), receipt_conveyor()
    )
    result = engine.run(300 * SECOND, 400 * SECOND)
    state = engine.unit_states["O2"]
    assert result.status == "complete"
    assert state.completed_picker_steps == 11 and state.completed_shipper_steps == 5
    assert state.cart_released_tick == state.picker_returned_tick == 20 * SECOND


def admitted_picker() -> tuple[CoordinatorEngine, HumanState]:
    engine = CoordinatorEngine(
        overlapping_profile(zero_approach=False, return_metres=3), receipt_conveyor()
    )
    engine.run(SECOND, SECOND)
    worker = engine.workers["P01"]
    assert worker.order_id == "O2" and worker.task == "picker"
    assert engine.unit_states["O2"].completed_picker_steps == 1
    return engine, worker


def test_cloned_worker_cannot_claim_actual_completion() -> None:
    engine, worker = admitted_picker()
    with pytest.raises(RuntimeError, match="NOT_ACTUAL_ENGINE_WORKER"):
        completed(engine, replace(worker), "travel_cart")
    assert engine.unit_states["O2"].completed_picker_steps == 1


def test_wrong_bound_picker_cannot_claim_another_orders_step() -> None:
    engine, _ = admitted_picker()
    worker = engine.workers["P02"]
    worker.order_id, worker.task = "O2", "picker"
    with pytest.raises(RuntimeError, match="PICKER_ACTOR_DIFFERS"):
        completed(engine, worker, "travel_cart")
    assert engine.unit_states["O2"].completed_picker_steps == 1


@pytest.mark.parametrize("count", [True, -1, 11])
def test_invalid_counter_never_indexes_a_declared_step(count: int) -> None:
    engine, worker = admitted_picker()
    engine.unit_states["O2"].completed_picker_steps = count
    with pytest.raises(RuntimeError, match="INVALID_COMPLETED_PICKER_STEP_COUNT"):
        completed(engine, worker, "travel_cart")


def test_actual_actor_still_requires_the_declared_step_kind() -> None:
    engine, worker = admitted_picker()
    with pytest.raises(RuntimeError, match="COMPLETED_PICKER_STEP_DIFFERS_FROM_DECLARED_PLAN"):
        completed(engine, worker, "return")
    assert engine.unit_states["O2"].completed_picker_steps == 1


@pytest.mark.parametrize("kind", ["pick", "deposit", "pickup_package"])
def test_foreign_role_cannot_set_unit_milestone_by_kind(kind: str) -> None:
    engine, _ = admitted_picker()
    worker = engine.workers["K06"]
    worker.order_id, worker.task = "O2", "packer_approach"
    before = engine.unit_states["O2"].view()
    completed(engine, worker, kind)
    assert engine.unit_states["O2"].view() == before
