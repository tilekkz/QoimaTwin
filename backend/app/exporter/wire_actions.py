"""Proposed 2.1 action semantics; geometry and simulation times stay authoritative."""

from typing import Any

from app.exporter.actions import project_actions
from app.exporter.wire_block_reasons import split_conveyor_waits
from app.exporter.wire_waits import resource_wait_actions
from app.simulation.engine import Engine

OPERATIONS = {
    "walk",
    "pick",
    "handoff",
    "pack",
    "scan",
    "receive",
    "load",
    "unload",
    "travel_empty",
    "travel_loaded",
    "wait_induction",
    "wait_pack_output",
    "wait_resource",
}


def wire_actions(engine: Engine, end_tick: int) -> list[dict[str, Any]]:
    result = project_actions(engine, end_tick)
    normalize_actions(engine, result, end_tick)
    result += resource_wait_actions(engine, end_tick)[0]
    return split_conveyor_waits(
        result,
        engine.ctx.grid.ticks_per_second,
        engine.ctx.ticks(engine.ctx.config.conveyor_tick_s),
    )


def normalize_actions(engine: Engine, result: list[dict[str, Any]], end_tick: int) -> None:
    roles = {a.actor_id: a.role for a in engine.ctx.inputs.actors.actors}
    totes = {
        e.entity_id: e.payload["tote_id"]
        for e in engine.ctx.recorder.events
        if e.kind == "order_assigned"
    }
    originals = {action.action_id: action for action in engine.ctx.recorder.actions}
    for action in result:
        original = originals.get(action["action_id"])
        action["open_ended"] = original is None or original.end_tick > end_tick
        action["scheduled_end_s"] = (
            original.end_tick / engine.ctx.grid.ticks_per_second if original else None
        )
        action["destination_node_id"] = (
            original.waypoints[-1].node_id if original and original.waypoints else None
        )
        operation = action["operation"]
        forklift = roles[action["actor_id"]] == "forklift_driver"
        action["carrying_cargo_id"] = _carrying(action, roles[action["actor_id"]], totes)
        action["reason"] = {"induction": "induction_full", "output": "pack_output_full"}.get(
            operation
        )
        if forklift:
            action["operation"] = _forklift_operation(operation)
        elif action["state"] == "TRAVEL":
            action["operation"] = "walk"
        elif operation in {"induction", "output"}:
            action["operation"] = (
                "wait_induction" if operation == "induction" else "wait_pack_output"
            )
        if action["operation"] not in OPERATIONS:
            raise ValueError(f"unknown proposed operation: {operation}")


def _carrying(action: dict[str, Any], role: str, totes: dict[str, str]) -> str | None:
    if role == "forklift_driver":
        return (
            action["entity_id"]
            if action["operation"] in {"to_dock", "to_reserve", "loading", "putaway"}
            else None
        )
    if role == "picker":
        return totes.get(action["entity_id"])
    if role == "shipper" and action["operation"] == "scan":
        return f"PCL_{action['entity_id']}"
    return None


def _forklift_operation(operation: str) -> str:
    return {
        "pickup": "load",
        "loading": "unload",
        "putaway": "unload",
        "to_pickup": "travel_empty",
        "to_home": "travel_empty",
        "to_dock": "travel_loaded",
        "to_reserve": "travel_loaded",
    }[operation]
