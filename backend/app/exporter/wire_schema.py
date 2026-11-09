"""Executable proposed schema; shared contracts remain unchanged until agreement."""

import copy
import json
from typing import Any

from jsonschema import ValidationError

from app.exporter.validation import REQUIRED, _validate_actions
from app.exporter.wire_actions import OPERATIONS
from app.exporter.wire_integrity import validate_integrity
from app.exporter.wire_plan_schema import pre_shift_schema
from app.exporter.wire_state_schema import nullable, state_schema
from app.exporter.wire_validate import validate_schema_fast
from app.settings import default_contracts_dir
from app.storage.canonical_json import sha256_hex

TEXT = {"type": "string", "minLength": 1}
NUMBER = {"type": "number", "minimum": 0}
TICK = {"type": "integer", "minimum": 0}
HASH = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
HASH_NAMES = (
    "layout",
    "config",
    "actors",
    "orders",
    "receipts",
    "initial_inventory",
    "assignment",
    "relocation_plan",
    "forecast_snapshot",
)


def object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def _payload(kind: str, fields: set[str]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for name in sorted(fields):
        if name in {"quantity", "outstanding_reservations", "slot_index"}:
            properties[name] = {"type": "integer", "minimum": 1 if name == "quantity" else 0}
        elif name.endswith("_ids"):
            properties[name] = {"type": "array", "items": TEXT}
        else:
            properties[name] = TEXT
    if kind == "actor_state_changed":
        properties["state"] = {
            "enum": ["IDLE", "TRAVEL", "BUSY_SERVICE", "BLOCKED", "WAIT_RESOURCE"]
        }
        properties["action_id"] = nullable(TEXT)
        properties["reason"] = nullable(TEXT)
    if kind == "stock_transferred":
        location = object_schema(
            {
                "kind": {
                    "enum": [
                        "external",
                        "pickface",
                        "reserve_slot",
                        "receiving",
                        "inbound_vehicle",
                        "reserve_staging",
                        "tote",
                        "pack_wip",
                        "parcel",
                        "dispatched",
                    ]
                },
                "ref": TEXT,
            }
        )
        properties["from"] = location
        properties["to"] = location
    return object_schema(properties)


def event_schema() -> dict[str, Any]:
    kinds = {
        **REQUIRED,
        "cell_moved": {"cargo_id", "from", "to"},
        "cargo_attached": {"cargo_id", "vehicle_id"},
        "cargo_detached": {"cargo_id", "vehicle_id", "container_id"},
        "cargo_placed": {"cargo_id", "container_id", "slot_index"},
        "cargo_removed": {"cargo_id", "container_id", "slot_index"},
        "receipt_arrived": {"receipt_id", "sku_id", "quantity"},
        "picked_last": {"order_id", "actor_id", "tote_id"},
        "stock_transferred": {"cargo_id", "sku_id", "lot_id", "quantity", "from", "to"},
        "actor_state_changed": {"actor_id", "state", "action_id", "reason"},
    }
    envelope = object_schema(
        {
            "seq": TICK,
            "at_tick": TICK,
            "at_s": NUMBER,
            "phase": {"type": "integer", "minimum": 0, "maximum": 4},
            "kind": {"enum": sorted(kinds)},
            "entity_id": TEXT,
            "payload": {"type": "object"},
        }
    )
    envelope["allOf"] = [
        {
            "if": {"properties": {"kind": {"const": kind}}},
            "then": {"properties": {"payload": _payload(kind, fields)}},
        }
        for kind, fields in sorted(kinds.items())
    ]
    return envelope


def proposal_schema() -> dict[str, Any]:
    legacy = json.loads((default_contracts_dir() / "run.schema.json").read_text(encoding="utf-8"))
    fields = copy.deepcopy(legacy["properties"])
    fields.update(
        {
            "schema_version": {"const": "2.1"},
            "contract_status": {"const": "proposal"},
            "identity": {"type": "object"},
            "ended_at_s": NUMBER,
            "ticks_per_second": {"type": "integer", "minimum": 1},
            "input_hashes": object_schema(dict.fromkeys(HASH_NAMES, HASH)),
            "metrics": {
                "type": "object",
                "required": ["at_horizon", "at_end"],
                "properties": {"at_horizon": {"type": "object"}, "at_end": {"type": "object"}},
            },
            "events": {"type": "array", "items": event_schema()},
            "conveyor_cells": {"type": "array", "items": TEXT, "uniqueItems": True},
            "replay_parameters": _replay_schema(),
            "locations": {"type": "array", "items": _location_schema()},
            "relocation_plan_id": nullable(HASH),
            "pre_shift": pre_shift_schema(),
        }
    )
    action, boundary = _action_schemas(fields["actions"]["items"])
    fields["boundary_actions"] = {"type": "array", "items": boundary}
    fields["snapshots"] = {
        "type": "array",
        "items": _snapshot_schema({"anyOf": [action, boundary]}),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:qoima:run:2.1:proposal",
        **object_schema(fields),
    }


def _action_schemas(action: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    action["properties"].update(
        {
            "operation": {"enum": sorted(OPERATIONS)},
            "carrying_cargo_id": {"type": ["string", "null"]},
            "reason": {"type": ["string", "null"]},
            "open_ended": {"type": "boolean"},
            "scheduled_end_s": nullable(NUMBER),
            "destination_node_id": nullable(TEXT),
            "blocked_since_tick": TICK,
        }
    )
    action["required"] += [
        "carrying_cargo_id",
        "reason",
        "open_ended",
        "scheduled_end_s",
        "destination_node_id",
    ]
    return action, _boundary_schema(action)


def _boundary_schema(action: dict[str, Any]) -> dict[str, Any]:
    boundary = copy.deepcopy(action)
    boundary["properties"].pop("waypoints")
    boundary["properties"]["end_s"] = {"type": "null"}
    boundary["properties"]["open_ended"] = {"const": True}
    boundary["required"] += ["pos"]
    return boundary


def _replay_schema() -> dict[str, Any]:
    mapping = {"type": "object", "additionalProperties": TEXT}
    return object_schema(
        {
            "pallet_max_age_ticks": TICK,
            "ticks_per_second": {"type": "integer", "minimum": 1},
            "pack_outlets": mapping,
            "induction_inlets": mapping,
            "merge_predecessors": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": TEXT},
            },
            "vehicles": {
                "type": "object",
                "additionalProperties": object_schema(
                    {"actor_id": TEXT, "route": {"enum": ["inbound", "outbound"]}}
                ),
            },
        }
    )


def _location_schema() -> dict[str, Any]:
    vec = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
    return object_schema(
        {
            "container_id": TEXT,
            "kind": {
                "enum": [
                    "pallet_position",
                    "pallet_queue",
                    "receiving_area",
                    "staging",
                    "dock",
                    "buffer",
                    "inlet",
                ]
            },
            "capacity": {"type": "integer", "minimum": 1},
            "positions": {"type": "array", "items": vec, "minItems": 1},
            "yaw": {"type": "number"},
            "conveyor_direction": {"enum": ["none", "source", "sink"]},
            "position_source": {"enum": ["observed_scene_anchor", "proposed_queue_grid"]},
        }
    )


def _snapshot_schema(action: dict[str, Any]) -> dict[str, Any]:
    return object_schema(
        {
            "at_s": NUMBER,
            "at_tick": TICK,
            "last_seq": {"type": "integer", "minimum": -1},
            "state_hash": HASH,
            "state": state_schema(action),
        }
    )


def validate_proposal(run: dict[str, Any]) -> None:
    try:
        validate_schema_fast(run)
    except ValidationError as exc:
        raise ValueError(f"proposed payload/schema invalid: {exc.message}") from exc
    if sha256_hex(run["identity"]) != run["run_id"]:
        raise ValueError("run identity hash mismatch")
    previous = (-1, -1)
    for seq, event in enumerate(run["events"]):
        key = (event["at_tick"], event["phase"])
        if key < previous or event["seq"] != seq:
            raise ValueError("invalid event ordering")
        if event["at_s"] != event["at_tick"] / run["ticks_per_second"]:
            raise ValueError("event timebase mismatch")
        previous = key
    _validate_actions(run["actions"])
    _validate_places(run)
    validate_integrity(run)
    for snapshot in run["snapshots"]:
        if sha256_hex(snapshot["state"]) != snapshot["state_hash"]:
            raise ValueError("snapshot state hash mismatch")


def _validate_places(run: dict[str, Any]) -> None:
    places = {place["container_id"]: place for place in run["locations"]}
    cells = set(run["conveyor_cells"])
    for place in places.values():
        if len(place["positions"]) != place["capacity"]:
            raise ValueError("container capacity/position count mismatch")
    for event in run["events"]:
        payload = event["payload"]
        if event["kind"] == "cell_moved":
            for endpoint, direction in [("from", "source"), ("to", "sink")]:
                target = payload[endpoint]
                if target not in cells and (
                    target not in places or places[target]["conveyor_direction"] != direction
                ):
                    raise ValueError(f"unknown or invalid conveyor container: {target}")
        elif event["kind"] == "cargo_placed":
            place = places.get(payload["container_id"])
            if place is None or payload["slot_index"] >= place["capacity"]:
                raise ValueError("invalid cargo container or slot index")
