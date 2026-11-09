"""The existing planning track stays on a separate before-shift calendar."""

from typing import Any

from app.exporter.wire_state_schema import COUNT, TEXT, array, nullable, obj

NUMBER = {"type": "number", "minimum": 0}


def pre_shift_schema() -> dict[str, Any]:
    return nullable(
        obj(
            {
                "calendar": {"const": "pre_shift"},
                "actor_id": TEXT,
                "ticks_per_second": {"type": "integer", "minimum": 1},
                "shift_start_s": {"type": "number"},
                "window_ticks": COUNT,
                "window_s": NUMBER,
                "actions": array(action_schema()),
                "transfers": array(transfer_schema()),
            }
        )
    )


def action_schema() -> dict[str, Any]:
    return obj(
        {
            "action_id": TEXT,
            "actor_id": TEXT,
            "swap_index": COUNT,
            "state": {"enum": ["TRAVEL", "BUSY_SERVICE"]},
            "operation": {"enum": ["relocation_walk", "relocation_take", "relocation_place"]},
            "start_tick": COUNT,
            "end_tick": COUNT,
            "start_s": NUMBER,
            "end_s": NUMBER,
            "node_ids": array(TEXT),
            "lot_id": nullable(TEXT),
        }
    )


def transfer_schema() -> dict[str, Any]:
    return obj(
        {
            "transfer_id": TEXT,
            "swap_index": COUNT,
            "step": {"type": "integer", "minimum": 1, "maximum": 6},
            "lot_id": TEXT,
            "sku_id": TEXT,
            "quantity": {"type": "integer", "minimum": 1},
            "from_location": TEXT,
            "to_location": TEXT,
            "take_start_tick": COUNT,
            "take_end_tick": COUNT,
            "place_start_tick": COUNT,
            "place_end_tick": COUNT,
        }
    )
