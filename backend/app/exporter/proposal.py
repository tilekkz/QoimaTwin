"""Opt-in 2.1 proposal, never a silent replacement of the shared v2.0 contract."""

from typing import Any

from app.exporter.catalog import cargo_catalog, initial_state
from app.exporter.identity import fingerprint
from app.exporter.wire_actions import wire_actions
from app.exporter.wire_boundary import boundary_actions
from app.exporter.wire_catalog import plan_metadata, replay_parameters
from app.exporter.wire_events import wire_events
from app.exporter.wire_locations import locations
from app.exporter.wire_schema import validate_proposal
from app.exporter.wire_snapshots import snapshots
from app.exporter.wire_transport import write_proposal_run as write_proposal_run
from app.simulation.engine import Engine, RunOutcome
from app.simulation.metrics_summary import summary
from app.storage.canonical_json import sha256_hex
from app.version import ENGINE_VERSION

__all__ = ["export_proposal", "validate_proposal", "write_proposal_run"]


def export_proposal(
    engine: Engine, outcome: RunOutcome, *, validate: bool = True
) -> dict[str, Any]:
    inputs = engine.ctx.inputs
    identity = {**fingerprint(inputs), "wire_version": "2.1-proposal"}
    actions = wire_actions(engine, outcome.end_tick)
    boundary = boundary_actions(engine, outcome.end_tick)
    observation_actions = sorted(actions + boundary, key=lambda a: (a["start_s"], a["action_id"]))
    events = wire_events(engine, outcome.end_tick, observation_actions)
    result = {
        "schema_version": "2.1",
        "contract_status": "proposal",
        "run_id": sha256_hex(identity),
        "identity": identity,
        "input_hashes": identity["hashes"],
        "engine_version": ENGINE_VERSION,
        "layout_version": inputs.layout.layout_version,
        "scenario_id": inputs.scenario.scenario_id,
        "experiment_type": inputs.experiment_type,
        "horizon_s": inputs.scenario.horizon_s,
        "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
        "ticks_per_second": engine.ctx.grid.ticks_per_second,
        "status": str(outcome.status),
        "termination_reason": str(outcome.termination),
        "actors": [
            a.model_dump(mode="json", exclude_none=True)
            for a in sorted(inputs.actors.actors, key=lambda a: a.actor_id)
        ],
        "cargo": cargo_catalog(engine),
        "initial_state": initial_state(engine),
        "locations": locations(engine),
        "conveyor_cells": list(engine.ctx.topology.cells),
        "replay_parameters": replay_parameters(engine),
        "events": events,
        "actions": actions,
        "boundary_actions": boundary,
        "snapshots": snapshots(engine, events, observation_actions),
        "metrics": summary(engine, outcome),
        **plan_metadata(engine),
    }
    if validate:
        validate_proposal(result)
    return result
