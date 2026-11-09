"""Prewritten causal boundary probes; execution is deferred by the user."""

from dataclasses import replace

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from app.v3.stock_ledger import StockLedger
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def _occupied_bench(profile: CoordinatorProfile) -> CoordinatorProfile:
    flow = profile.world.receipts.flow
    assert any(c.container_id == "P1" for c in flow.materials)
    flow = replace(
        flow,
        materials=tuple(
            replace(c, owner_id="bench05") if c.container_id == "P1" else c for c in flow.materials
        ),
    )
    receipts = replace(profile.world.receipts, flow=flow)
    return replace(profile, world=replace(profile.world, receipts=receipts))


def _stock_at(state: CoordinatorSnapshot, ledger: StockLedger) -> CoordinatorSnapshot:
    return replace(
        state,
        stock=ledger.snapshot(),
        inventory=ledger.inventory_snapshot(),
        balance=ledger.balance(),
    )


def test_helper_cannot_activate_on_an_occupied_physical_bench() -> None:
    profile, outcome = role_case(200 * SECOND)
    source = receipt_conveyor()
    original = freeze_hand_inputs(profile, source, 200 * SECOND, 200 * SECOND)
    build_coordinator_run(original, outcome)
    blocked = _occupied_bench(profile)
    inputs = freeze_hand_inputs(blocked, source, 200 * SECOND, 200 * SECOND)
    flow = blocked.world.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    assert ledger.contents("P1").container.owner_id == "bench05"
    assert not any(event.delta is not None for event in outcome.events)
    wrong = replace(
        outcome,
        at_horizon=_stock_at(outcome.at_horizon, ledger),
        at_end=_stock_at(outcome.at_end, ledger),
        checkpoints=tuple(_stock_at(state, ledger) for state in outcome.checkpoints),
    )
    with pytest.raises(ValueError):
        build_coordinator_run(inputs, wrong)


def test_cart_release_requires_the_actual_assigned_picker_even_at_the_same_node() -> None:
    profile, source = multi_profile(candidate=False), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, source, 110 * SECOND, 110 * SECOND)
    outcome = CoordinatorEngine(profile, source).run(110 * SECOND, 110 * SECOND)
    build_coordinator_run(inputs, outcome)
    flow = profile.world.receipts.flow
    assert next(a.home for a in flow.actors if a.actor_id == "P03") == flow.cart.home == "H"
    releases = [e for e in outcome.events if e.kind == "cart_released" and e.order_id == "O1"]
    assert len(releases) == 1 and releases[0].actor_id == "P01"
    wrong = replace(
        outcome,
        events=tuple(
            replace(e, actor_id="P03") if e.seq == releases[0].seq else e for e in outcome.events
        ),
    )
    with pytest.raises(ValueError):
        build_coordinator_run(inputs, wrong)
