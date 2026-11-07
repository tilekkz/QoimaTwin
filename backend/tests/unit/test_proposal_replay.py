"""Differential replay against independent settled engine snapshots."""

import copy
import dataclasses
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.contracts.scenario import Receipt
from app.exporter.proposal import export_proposal
from app.exporter.wire_replay import replay_snapshot
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from tests.unit.test_proposal_export import proposal as proposal


def test_every_checkpoint_replays_to_the_next_live_state(proposal: dict[str, Any]) -> None:
    checkpoints = proposal["snapshots"]
    for before, after in pairwise(checkpoints):
        actual = replay_snapshot(proposal, before, after["at_tick"])
        assert actual == after, f"replay {before['at_s']} -> {after['at_s']}"


def test_replay_does_not_mutate_source_checkpoint(proposal: dict[str, Any]) -> None:
    start = proposal["snapshots"][0]
    original = copy.deepcopy(start)
    replay_snapshot(proposal, start, proposal["snapshots"][1]["at_tick"])
    assert start == original


def test_replay_multiple_orders_and_blocked_receiving(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    orders = tuple(
        inputs.scenario.orders[0].model_copy(update={"order_id": f"R{i:03d}"}) for i in range(8)
    )
    sku = orders[0].lines[0].sku_id
    receipts = tuple(
        Receipt(receipt_id=f"RC{i}", arrival_s=10.0 + i * 10, sku_id=sku, quantity=25)
        for i in range(4)
    )
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(
            update={"horizon_s": 600.0, "orders": orders, "receipts": receipts}
        ),
        config=inputs.config.model_copy(
            update={
                "snapshot_interval_s": 7.0,
                "receiving_queue_capacity": 2,
                "reserve_staging_capacity": 1,
            }
        ),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_proposal(engine, engine.run())
    checkpoints = run["snapshots"]
    positions = next(s for s in checkpoints if s["at_s"] == 119)["state"]["placements"]
    assert positions["IN_RC1"]["slot_index"] == 1
    assert positions["IN_RC2"]["slot_index"] == 0  # slot0 is freed at pickup10+90+3+15=118
    for before, after in pairwise(checkpoints):
        assert replay_snapshot(run, before, after["at_tick"]) == after, (
            f"{before['at_s']} -> {after['at_s']}"
        )


def test_replay_seeks_across_multiple_intervals(proposal: dict[str, Any]) -> None:
    start = proposal["snapshots"][0]
    for target in proposal["snapshots"][2::3]:
        assert replay_snapshot(proposal, start, target["at_tick"]) == target


@pytest.mark.parametrize("horizon", [32.8, 52.0, 68.1, 76.1, 77.0, 124.0, 432.0, 440.0])
def test_replay_exact_cutoff_transition(
    bundle: ContractBundle, contracts_dir: Path, horizon: float
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": horizon}),
        config=inputs.config.model_copy(update={"max_drain_s": 0, "snapshot_interval_s": horizon}),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_proposal(engine, engine.run())
    before, after = run["snapshots"]
    assert replay_snapshot(run, before, after["at_tick"]) == after
