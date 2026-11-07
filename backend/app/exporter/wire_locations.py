"""Explicit scene anchors and visibly unapproved queue grids for the 2.1 proposal."""

from math import pi
from typing import Any

from app.simulation.engine import Engine


def _place(
    name: str, kind: str, anchor: list[float], capacity: int, *, observed: bool = False
) -> dict[str, Any]:
    return {
        "container_id": name,
        "kind": kind,
        "capacity": capacity,
        "positions": [
            [round(anchor[0] + (i % 4) * 1.2, 3), anchor[1], round(anchor[2] + (i // 4) * 1.2, 3)]
            for i in range(capacity)
        ],
        "yaw": -pi / 2,
        "conveyor_direction": "none",
        "position_source": "observed_scene_anchor" if observed else "proposed_queue_grid",
    }


def locations(engine: Engine) -> list[dict[str, Any]]:
    cfg, layout = engine.ctx.config, engine.ctx.inputs.layout
    result = [
        _place("OPEN_PALLET", "pallet_position", [64.92, 0.0, 6.0], 1, observed=True),
        _place(
            "SEALED_PALLETS", "pallet_queue", [64.92, 0.0, 8.0], cfg.sealed_pallet_queue_capacity
        ),
        _place("RECEIVING_AREA", "receiving_area", [4.0, 0.0, 36.92], cfg.receiving_queue_capacity),
        _place("RESERVE_STAGING", "staging", [4.0, 0.0, 14.92], cfg.reserve_staging_capacity),
        _place("DOCK_IN", "dock", [0.0, 0.0, 36.0], 1, observed=True),
        _place("DOCK_OUT", "dock", [71.08, 0.0, 2.0], 1, observed=True),
        _place(
            "SHIPPING",
            "buffer",
            list(layout.conveyor.terminal.shipping_buffer_pos),
            cfg.shipping_buffer_capacity,
        ),
        _place("inlet", "inlet", list(layout.inductions[0].handoff_anchor), 1, observed=True),
    ]
    for station in layout.pack_stations:
        result.append(
            _place(station.pack_id, "buffer", list(station.input_anchor), cfg.pack_buffer_capacity)
        )
        result.append(
            _place(
                f"output:{station.pack_id}", "inlet", list(station.output_anchor), 1, observed=True
            )
        )
    for induction in layout.inductions:
        result.append(
            _place(f"inlet:{induction.induction_id}", "inlet", list(induction.handoff_anchor), 1)
        )
    for place in result:
        if place["kind"] == "inlet":
            place["conveyor_direction"] = "source"
        elif place["kind"] == "buffer":
            place["conveyor_direction"] = "sink"
    return result
