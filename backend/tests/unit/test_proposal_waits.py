"""One resource-wait policy governs exact-tick metrics and public action descriptors."""

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.exporter.proposal import export_proposal
from app.exporter.wire_replay import replay_snapshot
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from tests.unit.test_proposal_export import proposal as proposal


def _limited_run(bundle: ContractBundle, contracts: Path, horizon: float) -> dict[str, Any]:
    inputs = fixture_inputs(bundle, load_fixture(contracts))
    first = inputs.scenario.orders[0]
    second = first.model_copy(update={"order_id": "SECOND"})
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(
            update={"horizon_s": horizon, "orders": (first, second)}
        ),
        config=inputs.config.model_copy(
            update={"totes_total": 1, "max_drain_s": 0, "snapshot_interval_s": horizon}
        ),
    )
    engine = Engine(inputs, check_invariants=True)
    return export_proposal(engine, engine.run())


def test_resource_wait_is_bounded_by_queued_work(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    run = _limited_run(bundle, contracts_dir, 60.0)
    waits = [a for a in run["actions"] if a["state"] == "WAIT_RESOURCE"]
    assert [(a["actor_id"], a["start_s"], a["end_s"]) for a in waits] == [
        ("P02", 0.0, 33.0),
        ("P01", 33.0, 60.0),
    ]
    assert sum(a["end_s"] - a["start_s"] for a in waits) == pytest.approx(60)
    for name in ("at_horizon", "at_end"):
        window = run["metrics"][name]
        assert window["labor_by_role"]["picker"]["wait_resource_s"] == pytest.approx(60)
        assert window["utilization_by_role"]["picker"]["wait_resource"] == pytest.approx(1 / 12)
    assert all(a["reason"] == "tote_unavailable" and a["carrying_cargo_id"] is None for a in waits)


def test_new_resource_wait_at_cutoff_has_only_boundary_descriptor(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    run = _limited_run(bundle, contracts_dir, 33.0)
    boundary = next(a for a in run["boundary_actions"] if a["actor_id"] == "P01")
    assert boundary["state"] == "WAIT_RESOURCE"
    assert boundary["start_s"] == 33.0 and boundary["end_s"] is None
    before, after = run["snapshots"]
    actor = next(a for a in after["state"]["actors"] if a["actor_id"] == "P01")
    assert actor["action"] == boundary
    assert replay_snapshot(run, before, after["at_tick"]) == after


def test_ordinary_idle_is_not_a_resource_wait(proposal: dict[str, Any]) -> None:
    assert not any(action["state"] == "WAIT_RESOURCE" for action in proposal["actions"])
