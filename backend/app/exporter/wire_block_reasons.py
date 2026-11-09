"""Split clock-grid waiting from actual finite conveyor admission blockage."""

from typing import Any


def split_conveyor_waits(
    actions: list[dict[str, Any]], tps: int, step_ticks: int
) -> list[dict[str, Any]]:
    result = []
    for source in actions:
        action = dict(source)
        if action["state"] != "BLOCKED" or action["operation"] not in {
            "wait_induction",
            "wait_pack_output",
        }:
            result.append(action)
            continue
        start = round(action["start_s"] * tps)
        action["blocked_since_tick"] = start
        attempt = ((start + step_ticks - 1) // step_ticks) * step_ticks
        if attempt == start:
            result.append(action)
            continue
        end = action["end_s"]
        action["reason"] = "awaiting_conveyor_tick"
        if end is not None and round(end * tps) > attempt:
            result.append(
                {
                    **action,
                    "action_id": f"{action['action_id']}:tick",
                    "end_s": attempt / tps,
                    "open_ended": False,
                }
            )
            result.append(
                {
                    **action,
                    "action_id": f"{action['action_id']}:capacity",
                    "start_s": attempt / tps,
                    "reason": source["reason"],
                }
            )
        else:
            result.append(action)
    return sorted(result, key=lambda action: (action["start_s"], action["action_id"]))
