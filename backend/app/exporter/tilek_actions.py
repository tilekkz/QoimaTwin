"""Tilek operation names; ownership still comes from physical handoff records."""

from typing import Any

from app.simulation.engine import Engine


def visual_actions(engine: Engine, actions: list[dict[str, Any]]) -> None:
    drivers = {v.driver_actor_id for v in engine.ctx.inputs.actors.vehicles}
    for action in actions:
        if action["actor_id"] not in drivers:
            continue
        operation = action["operation"]
        if action["state"] == "TRAVEL":
            action["operation"] = "drive"
            if operation in {"to_pickup", "to_home", "travel_empty"}:
                action["entity_id"] = None
        else:
            action["operation"] = {
                "pickup": "loading",
                "loading": "unloading",
                "putaway": "unloading",
            }.get(operation, operation)
