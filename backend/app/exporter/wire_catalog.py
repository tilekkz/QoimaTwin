"""Small immutable replay parameters included in the proposed run catalog."""

from typing import Any

from app.simulation.engine import Engine


def plan_metadata(engine: Engine) -> dict[str, Any]:
    plan = engine.ctx.inputs.relocation_json()
    if plan is None:
        return {"relocation_plan_id": None, "pre_shift": None}
    data = plan.to_dict()
    return {"relocation_plan_id": plan.sha256, "pre_shift": data["relocation"]}


def replay_parameters(engine: Engine) -> dict[str, Any]:
    return {
        "pallet_max_age_ticks": engine.ctx.ticks(engine.ctx.config.pallet_max_age_s),
        "ticks_per_second": engine.ctx.grid.ticks_per_second,
        "pack_outlets": dict(engine.ctx.topology.pack_outlets),
        "induction_inlets": dict(engine.ctx.topology.induction_inlets),
        "merge_predecessors": {
            target: list(sources)
            for target, sources in engine.ctx.topology.predecessors.items()
            if len(sources) > 1
        },
        "vehicles": {
            v.vehicle_id: {"actor_id": v.driver_actor_id, "route": v.graph_id}
            for v in engine.ctx.inputs.actors.vehicles
        },
    }
