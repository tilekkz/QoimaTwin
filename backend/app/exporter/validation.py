"""Shared JSON Schema plus payload and interval checks not expressed by v2."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from app.settings import default_contracts_dir

REQUIRED = {
    "order_arrived": {"order_id"},
    "order_rejected_inventory": {"order_id", "reason"},
    "order_assigned": {"order_id", "actor_id", "tote_id"},
    "stock_reserved": {"order_id", "sku_id", "slot_id", "lot_id", "quantity"},
    "sku_picked": {"order_id", "sku_id", "slot_id", "lot_id", "quantity", "actor_id", "tote_id"},
    "handoff_ready": {"order_id", "actor_id", "tote_id", "induction_id", "target_pack_id"},
    "tote_inducted": {
        "order_id",
        "actor_id",
        "tote_id",
        "induction_id",
        "target_pack_id",
        "cell_id",
    },
    "pack_started": {"order_id", "actor_id", "tote_id", "pack_id"},
    "order_packed": {"order_id", "actor_id", "tote_id", "pack_id", "parcel_id"},
    "parcel_outfed": {"order_id", "actor_id", "pack_id", "parcel_id", "cell_id"},
    "shipping_arrived": {"order_id", "parcel_id"},
    "parcel_scanned": {"order_id", "parcel_id", "pallet_id", "actor_id"},
    "pallet_sealed": {"pallet_id", "parcel_ids", "order_ids"},
    "pallet_seal_pending": {"pallet_id", "trigger", "outstanding_reservations"},
    "order_dispatched": {"order_id", "parcel_id", "pallet_id", "actor_id", "dock_id"},
    "receipt_accepted": {"receipt_id", "pallet_id", "sku_id", "quantity", "ledger_to"},
    "receipt_processed": {"receipt_id", "pallet_id", "sku_id", "quantity", "actor_id"},
    "pallet_putaway": {
        "receipt_id",
        "pallet_id",
        "sku_id",
        "quantity",
        "actor_id",
        "ledger_from",
        "ledger_to",
    },
}
CELL_FIELDS = {"cargo_id", "cell_id", "transition_id", "from_container_id", "to_container_id"}


@lru_cache(maxsize=8)
def _validator(schema_text: str) -> Any:
    return jsonschema.Draft202012Validator(json.loads(schema_text))


def validate_run(run: dict[str, Any], contracts_dir: Path | None = None) -> None:
    path = (contracts_dir or default_contracts_dir()) / "run.schema.json"
    _validator(path.read_text(encoding="utf-8")).validate(run)
    previous = (-1.0, -1, -1)
    for seq, event in enumerate(run["events"]):
        key = (event["at_s"], event["phase"], event["seq"])
        if key < previous or event["seq"] != seq or not 0 <= event["phase"] <= 4:
            raise ValueError("invalid event sequence or phase")
        previous = key
        required = CELL_FIELDS if event["kind"].startswith("cell_") else REQUIRED[event["kind"]]
        if not required <= event["payload"].keys():
            raise ValueError(f"{event['kind']}: missing payload fields")
        if "quantity" in event["payload"] and event["payload"]["quantity"] <= 0:
            raise ValueError("quantity must be positive")
    _validate_actions(run["actions"])
    _validate_transfers(run)


def _validate_transfers(run: dict[str, Any]) -> None:
    events = run["events"]
    seen: set[str] = set()
    cargo_ids = {c["cargo_id"] for c in run["cargo"]}
    for index, event in enumerate(events):
        if event["kind"] != "cell_exited":
            if event["kind"] == "cell_entered" and (
                index == 0 or events[index - 1]["kind"] != "cell_exited"
            ):
                raise ValueError("orphan cell_entered")
            continue
        if index + 1 == len(events) or events[index + 1]["kind"] != "cell_entered":
            raise ValueError("orphan cell_exited")
        entered = events[index + 1]
        payload, other = event["payload"], entered["payload"]
        shared = CELL_FIELDS - {"cell_id"}
        if (
            payload["cell_id"] != payload["from_container_id"]
            or other["cell_id"] != other["to_container_id"]
            or event["entity_id"] != payload["cargo_id"]
            or entered["entity_id"] != payload["cargo_id"]
        ):
            raise ValueError("invalid transfer endpoint or entity")
        if any(payload[key] != other[key] for key in shared):
            raise ValueError("mismatched transfer pair")
        transition = payload["transition_id"]
        if transition in seen or payload["cargo_id"] not in cargo_ids:
            raise ValueError("duplicate transition or unknown cargo")
        seen.add(transition)
        if event["at_s"] != entered["at_s"] or event["phase"] != 2 or entered["phase"] != 2:
            raise ValueError("transfer pair must be atomic in phase 2")


def _validate_actions(actions: list[dict[str, Any]]) -> None:
    ends: dict[str, float] = {}
    for action in actions:
        start, end = action["start_s"], action["end_s"]
        if end <= start or start < ends.get(action["actor_id"], 0):
            raise ValueError("invalid action interval or overlap")
        ends[action["actor_id"]] = end
        travel = action["state"] == "TRAVEL"
        if travel != ("waypoints" in action) or travel == ("pos" in action):
            raise ValueError("invalid action geometry")
        if travel:
            points = action["waypoints"]
            times = [p["at_s"] for p in points]
            if len(points) < 2 or times != sorted(times) or times[0] != start or times[-1] != end:
                raise ValueError("invalid travel waypoints")
