"""Clock quantization is distinct from exhausted inlet/output capacity."""

from typing import Any

from app.exporter.wire_block_reasons import split_conveyor_waits


def test_block_waits_for_next_tick_before_capacity_is_known() -> None:
    action: dict[str, Any] = {
        "action_id": "A1",
        "state": "BLOCKED",
        "operation": "wait_induction",
        "start_s": 1.2,
        "end_s": 4.0,
        "reason": "induction_full",
        "open_ended": False,
    }
    first, second = split_conveyor_waits([action], 10, 10)
    assert (first["start_s"], first["end_s"], first["reason"]) == (
        1.2,
        2.0,
        "awaiting_conveyor_tick",
    )
    assert (second["start_s"], second["end_s"], second["reason"]) == (2.0, 4.0, "induction_full")
    assert first["action_id"] != second["action_id"]


def test_boundary_block_does_not_invent_a_future_interval() -> None:
    action: dict[str, Any] = {
        "action_id": "OPEN_P01",
        "state": "BLOCKED",
        "operation": "wait_induction",
        "start_s": 32.8,
        "end_s": None,
        "reason": "induction_full",
        "open_ended": True,
    }
    result = split_conveyor_waits([action], 10, 10)
    assert len(result) == 1
    assert result[0]["reason"] == "awaiting_conveyor_tick"
    assert result[0]["end_s"] is None
