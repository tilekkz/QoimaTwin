"""Receipt stock handoffs require an actual matching actor operation start and completion."""

from app.storage.canonical_json import canonical_bytes
from app.v3.interface import Json


def completed_operation(event: Json, events: list[Json], kind: str) -> Json:
    key, tick, actor = event["order_id"], event["tick"], event["actor_id"]
    completed = [
        e
        for e in events
        if e["order_id"] == key
        and e["tick"] == tick
        and e["kind"] == "operation_completed"
        and e["operation"] is not None
        and e["operation"]["kind"] == kind
    ]
    if len(completed) != 1 or completed[0]["actor_id"] != actor:
        raise ValueError("Receipt handoff lacks actual completion by its assigned actor")
    operation: Json = completed[0]["operation"]
    if operation["order_id"] != key or operation["planned_end_tick"] != tick:
        raise ValueError("Receipt completion belongs to another job or planned end")
    started = [
        e
        for e in events
        if e["kind"] == "operation_started"
        and e["order_id"] == key
        and e["actor_id"] == actor
        and e["tick"] == operation["start_tick"]
        and canonical_bytes(e["operation"]) == canonical_bytes(operation)
    ]
    if len(started) != 1:
        raise ValueError("Receipt completion differs from its actual started operation")
    return operation


def validate_handoff(catalog: Json, event: Json, events: list[Json]) -> None:
    operations = {
        "receipt_buffered": ("receipt_place_buffer", "place_tick"),
        "receipt_buffer_picked": ("receipt_pick_buffer", "pickup_tick"),
        "receipt_putaway": ("receipt_place_slot", "place_tick"),
    }
    if event["kind"] not in operations:
        return
    kind, duration = operations[event["kind"]]
    operation = completed_operation(event, events, kind)
    process = catalog["receipt_process"]
    if event["tick"] - operation["start_tick"] != process[duration]:
        raise ValueError("Receipt handling duration differs from the explicit process")
    offer = next(
        r
        for r in catalog["declared_receipts"]
        if r["definition"]["receipt_id"] == event["order_id"]
    )
    owner = (
        offer["slot_owner_id"]
        if kind == "receipt_place_slot"
        else event["receipt"]["buffer_owner_id"]
    )
    place = next(p for p in process["places"] if p["owner_id"] == owner)
    if operation["source_node"] != place["node_id"] or operation["target_node"] != place["node_id"]:
        raise ValueError("Receipt handling completion is not at its actual physical place")
