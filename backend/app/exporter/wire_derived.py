"""Derived public milestones and inventory moves anchored to authoritative domain events."""

from collections import Counter, defaultdict
from collections.abc import Iterator
from typing import Any

from app.simulation.engine import Engine

type Row = dict[str, Any]
type Key = tuple[int, int, int, int]


def _row(engine: Engine, key: Key, kind: str, entity: str, payload: Row) -> tuple[Key, Row]:
    return key, {
        "at_tick": key[0],
        "at_s": key[0] / engine.ctx.grid.ticks_per_second,
        "phase": key[1],
        "kind": kind,
        "entity_id": entity,
        "payload": payload,
    }


def milestones(engine: Engine) -> Iterator[tuple[Key, Row]]:
    required = {
        o.order_id: sum(line.quantity for line in o.lines)
        for o in engine.ctx.inputs.scenario.orders
    }
    picked: Counter[str] = Counter()
    for event in engine.ctx.recorder.events:
        if event.kind != "sku_picked":
            continue
        picked[event.entity_id] += event.payload["quantity"]
        if picked[event.entity_id] == required[event.entity_id]:
            payload = {k: event.payload[k] for k in ("order_id", "actor_id", "tote_id")}
            yield _row(
                engine,
                (event.at_tick, int(event.phase), event.seq, 9),
                "picked_last",
                event.entity_id,
                payload,
            )


def stock_moves(engine: Engine) -> Iterator[tuple[Key, Row]]:
    picked: dict[str, list[Row]] = defaultdict(list)
    for event in engine.ctx.recorder.events:
        p, kind = event.payload, event.kind
        if kind == "sku_picked":
            picked[event.entity_id].append(p)
            legs = ("pickface", p["slot_id"], "tote", p["tote_id"])
            holdings = [p]
        elif kind in {"pack_started", "order_packed", "order_dispatched"}:
            legs = _order_leg(kind, p)
            holdings = picked[event.entity_id]
        elif kind == "receipt_accepted":
            legs = ("external", p["receipt_id"], "receiving", p["pallet_id"])
            holdings = [{**p, "lot_id": p["receipt_id"]}]
        elif kind == "pallet_putaway":
            legs = ("inbound_vehicle", p["actor_id"], "reserve_staging", p["pallet_id"])
            holdings = [{**p, "lot_id": p["receipt_id"]}]
        else:
            continue
        for index, holding in enumerate(holdings):
            key = (event.at_tick, int(event.phase), event.seq, 10 + index)
            payload = _stock_payload(holding, legs)
            yield _row(engine, key, "stock_transferred", payload["cargo_id"], payload)


def _order_leg(kind: str, p: Row) -> tuple[str, str, str, str]:
    if kind == "pack_started":
        return "tote", p["tote_id"], "pack_wip", p["pack_id"]
    if kind == "order_packed":
        return "pack_wip", p["pack_id"], "parcel", p["parcel_id"]
    return "parcel", p["parcel_id"], "dispatched", p["dock_id"]


def _stock_payload(holding: Row, legs: tuple[str, str, str, str]) -> Row:
    source_kind, source, target_kind, target = legs
    cargo = target if target_kind in {"tote", "parcel"} else source
    if source_kind not in {"tote", "parcel"} and target_kind not in {"tote", "parcel"}:
        cargo = holding.get("pallet_id", source)
    return {
        "cargo_id": cargo,
        "sku_id": holding["sku_id"],
        "lot_id": holding["lot_id"],
        "quantity": holding["quantity"],
        "from": {"kind": source_kind, "ref": source},
        "to": {"kind": target_kind, "ref": target},
    }


def receipt_pickups(engine: Engine, end_tick: int) -> Iterator[tuple[Key, Row]]:
    receipts = {
        e.payload["pallet_id"]: e.payload
        for e in engine.ctx.recorder.events
        if e.kind == "receipt_accepted"
    }
    rows = []
    for action in engine.ctx.recorder.actions:
        if (
            action.operation != "pickup"
            or action.end_tick > end_tick
            or action.entity_id not in receipts
        ):
            continue
        p = receipts[action.entity_id]
        holding = {**p, "lot_id": p["receipt_id"]}
        legs = ("receiving", p["pallet_id"], "inbound_vehicle", action.actor_id)
        key = (action.end_tick, 0, -1, 100)
        rows.append(
            _row(engine, key, "stock_transferred", p["pallet_id"], _stock_payload(holding, legs))
        )
    yield from sorted(rows, key=lambda pair: pair[0])


def actor_changes(engine: Engine, actions: list[Row]) -> Iterator[tuple[Key, Row]]:
    changes: dict[tuple[int, str], Row] = {}
    tps = engine.ctx.grid.ticks_per_second
    for action in reversed(actions):
        actor = action["actor_id"]
        if not action["open_ended"]:
            changes.setdefault(
                (round(action["end_s"] * tps), actor),
                {"actor_id": actor, "state": "IDLE", "action_id": None, "reason": None},
            )
        changes[(round(action["start_s"] * tps), actor)] = {
            "actor_id": actor,
            "state": action["state"],
            "action_id": action["action_id"],
            "reason": action["reason"],
        }
    for index, ((tick, actor), payload) in enumerate(sorted(changes.items())):
        yield _row(engine, (tick, 4, index, 0), "actor_state_changed", actor, payload)
