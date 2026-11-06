"""One-hour offered load from 05 T6; differential replay uses no engine-derived oracle."""

from __future__ import annotations

from itertools import groupby
from typing import Any

import pytest

from app.contracts.assignment import Assignment
from app.contracts.loader import ContractBundle
from app.data.scenario_materializer import Profile, materialize
from app.exporter.run import export_run
from app.simulation.context import RunInputs
from app.simulation.engine import Engine
from app.storage.canonical_json import sha256_hex

pytestmark = [pytest.mark.acceptance, pytest.mark.performance]
type EventRow = dict[str, Any]


def _apply_cell_batch(
    occupancy: dict[str, str], events: list[EventRow], physical_cells: set[str]
) -> None:
    # All exits precede all entries: moves in one phase share the same pre-tick occupancy.
    for event in events:
        payload = event["payload"]
        cell, cargo = payload["cell_id"], payload["cargo_id"]
        if event["kind"] == "cell_exited" and cell in physical_cells:
            assert occupancy.pop(cell) == cargo, (event["seq"], cell, cargo)
    for event in events:
        payload = event["payload"]
        cell, cargo = payload["cell_id"], payload["cargo_id"]
        if event["kind"] == "cell_entered" and cell in physical_cells:
            assert cell not in occupancy, (event["seq"], cell, cargo)
            assert cargo not in occupancy.values(), (event["seq"], cell, cargo)
            occupancy[cell] = cargo


def _assert_snapshot_cells(engine: Engine, events: list[EventRow]) -> None:
    occupancy: dict[str, str] = {}
    cells = set(engine.ctx.topology.cells)
    snapshots = iter(engine.checkpoints.snapshots)
    snapshot = next(snapshots, None)
    transfers = [event for event in events if event["kind"] in {"cell_exited", "cell_entered"}]
    for (at_s, phase), batch in groupby(
        transfers, key=lambda event: (event["at_s"], event["phase"])
    ):
        assert phase == 2
        at_tick = int(at_s * engine.ctx.grid.ticks_per_second)
        while snapshot is not None and snapshot.at_tick < at_tick:
            assert occupancy == dict(snapshot.state["conveyor"]["cells"]), snapshot.at_tick
            snapshot = next(snapshots, None)
        _apply_cell_batch(occupancy, list(batch), cells)
        while snapshot is not None and snapshot.at_tick == at_tick:
            assert occupancy == dict(snapshot.state["conveyor"]["cells"]), snapshot.at_tick
            snapshot = next(snapshots, None)
    while snapshot is not None:
        assert occupancy == dict(snapshot.state["conveyor"]["cells"]), snapshot.at_tick
        snapshot = next(snapshots, None)
    assert occupancy == engine.conveyor.occupancy


def _mass_run(bundle: ContractBundle, profile: Profile, offered: int) -> tuple[str, str]:
    scenario = materialize(profile, 3600, bundle.config).scenario
    assignment = Assignment.from_json_text(
        (bundle.directory / "assignment.example.json").read_bytes()
    )
    inputs = RunInputs(bundle.layout, bundle.config, bundle.actors, assignment, scenario)
    engine = Engine(inputs, check_invariants=True)
    run = export_run(engine, engine.run())
    assert len(scenario.orders) == offered
    assert engine.metrics.counts()["arrived_total"] == offered
    assert engine.ctx.ledger.check_conservation() == []
    _assert_snapshot_cells(engine, run["events"])
    return str(run["run_id"]), sha256_hex(run["events"])


@pytest.mark.parametrize(("profile", "offered"), [("large-normal", 240), ("large-peak", 600)])
def test_T6_hourly_mass_flow_is_reproducible_with_invariants_and_projection(
    bundle: ContractBundle, profile: Profile, offered: int
) -> None:
    assert _mass_run(bundle, profile, offered) == _mass_run(bundle, profile, offered)
