"""Bind frozen physical placements to the existing generic Tilek payload hook."""

from bisect import bisect_right
from collections.abc import Iterator
from typing import Any

from app.exporter.wire_events import _attachments
from app.exporter.wire_locations import locations
from app.exporter.wire_placements import placements
from app.exporter.wire_positions import apply_position
from app.simulation.engine import Engine

type Row = dict[str, Any]
type Key = tuple[int, int, int, int, int]


def _base_keys(engine: Engine) -> list[Key]:
    keys = [(e.at_tick, int(e.phase), e.seq, 1, 0) for e in engine.ctx.recorder.events]
    for index, move in enumerate(engine.conveyor.transfers):
        keys.extend((move.at_tick, 2, move.event_offset, 0, 2 * index + side) for side in (0, 1))
    return sorted(keys)


def _transition(engine: Engine, tick: int, actor: str) -> Row:
    following = next(
        (a for a in engine.ctx.recorder.actions if a.actor_id == actor and a.start_tick == tick),
        None,
    )
    return {
        "actor_id": actor,
        "state": str(following.state) if following else "IDLE",
        "action_id": following.action_id if following else None,
        "transition": "physical_handoff",
    }


def _physical(engine: Engine, end_tick: int) -> Iterator[tuple[Key, Row]]:
    drivers = {v.vehicle_id: v.driver_actor_id for v in engine.ctx.inputs.actors.vehicles}
    for key, row in _attachments(engine, end_tick):
        row["payload"].update(_transition(engine, key[0], drivers[row["payload"]["vehicle_id"]]))
        yield (*key[:3], 0, key[3]), row
    for key, row in placements(engine, end_tick):
        if row["at_tick"] <= end_tick:
            yield (*key, 0), row


def _binding(position: Row, places: dict[str, Row]) -> Row:
    if position.get("vehicle_id"):
        return {
            "stage": "vehicle",
            "attachment": {
                "kind": "vehicle",
                "id": position["vehicle_id"],
                "offset": [0.0, 0.0, 0.0],
            },
        }
    container = position["container_id"]
    slot = position.get("slot_index") or 0
    place = places[container]
    return {
        "pos": place["positions"][slot],
        "stage": container,
        "container_id": container,
        "slot_index": slot,
        "position_source": place["position_source"],
        "attachment": {"kind": "world"},
    }


def _derived(engine: Engine, row: Row, places: dict[str, Row], positions: Row) -> Row | None:
    kind, payload = row["kind"], row["payload"]
    apply_position(positions, row)
    if kind == "cargo_removed":
        return None  # The next owner/hide milestone performs the visual change.
    cargo = payload["cargo_id"]
    binding = _binding(positions[cargo], places)
    if kind == "cargo_placed":
        # Placement changes at domain milestones are enriched there instead.
        if payload["container_id"] != "OPEN_PALLET":
            return None
        transition = _scan_transition(engine, row["at_tick"], cargo)
        if transition is None:
            return None
    else:
        transition = {k: payload[k] for k in ("actor_id", "state", "action_id", "transition")}
    return {
        "at_s": row["at_s"],
        "phase": row["phase"],
        "kind": "actor_state_changed",
        "entity_id": transition["actor_id"],
        "payload": {
            **transition,
            **binding,
            "cargo_id": cargo,
            "at_tick": row["at_tick"],
            "visual_projection": True,
            "physical_event": kind,
        },
    }


def _scan_transition(engine: Engine, tick: int, cargo: str) -> Row | None:
    pallets = {
        e.entity_id: e.payload["pallet_id"]
        for e in engine.ctx.recorder.events
        if e.kind == "parcel_scanned"
    }
    live = engine.shipping.open_pallet
    for action in engine.ctx.recorder.actions:
        if action.operation != "scan" or action.start_tick != tick:
            continue
        pallet = pallets.get(action.entity_id or "", live.pallet_id if live else None)
        if pallet == cargo:
            return {
                "actor_id": action.actor_id,
                "state": str(action.state),
                "action_id": action.action_id,
                "transition": "scan_started",
            }
    return None


def _enrich(
    row: Row, positions: Row, pending: dict[tuple[int, str], Row], places: dict[str, Row]
) -> None:
    payload, kind = row["payload"], row["kind"]
    cargo = payload.get("pallet_id")
    if kind not in {"parcel_scanned", "pallet_sealed", "receipt_accepted", "pallet_putaway"}:
        return
    position = pending.get((payload["at_tick"], cargo), positions.get(cargo))
    if position is None:
        return
    payload.update(_binding(position, places))
    payload.update(cargo_id=cargo, visual_projection=True)


def visual_events(engine: Engine, end_tick: int, source: list[Row], provenance: Row) -> list[Row]:
    places = {p["container_id"]: p for p in locations(engine)}
    physical = list(_physical(engine, end_tick))
    pending = {
        (r["at_tick"], r["entity_id"]): r["payload"]
        for _, r in physical
        if r["kind"] == "cargo_placed"
    }
    combined = [(key, False, row) for key, row in zip(_base_keys(engine), source, strict=True)]
    combined.extend((key, True, row) for key, row in physical)
    positions: Row = {}
    result = []
    for _, derived, row in sorted(combined, key=lambda item: item[0]):
        if derived:
            projected = _derived(engine, row, places, positions)
            if projected is None:
                continue
            row = projected
        else:
            row["payload"]["source_seq"] = row["seq"]
            _enrich(row, positions, pending, places)
        result.append(row)
    # Initial actor state is a real boundary, also carrying schema-safe provenance.
    actor = min(a.actor_id for a in engine.ctx.inputs.actors.actors)
    initial = {
        "at_s": 0.0,
        "phase": 0,
        "kind": "actor_state_changed",
        "entity_id": actor,
        "payload": {
            **_transition(engine, 0, actor),
            "transition": "initial_state",
            "visual_projection": provenance,
            "at_tick": 0,
        },
    }
    result.insert(0, initial)
    return [{**row, "seq": seq} for seq, row in enumerate(result)]


def bind_snapshots(snapshots: list[Row], events: list[Row], provenance: Row) -> None:
    from app.storage.canonical_json import sha256_hex

    times = [e["at_s"] for e in events]
    for snapshot in snapshots:
        state = snapshot["state"]
        state["source_checkpoint"] = dict(state["checkpoint"])
        state["visual_projection"] = provenance
        checkpoint = state.pop("checkpoint")
        checkpoint["last_seq"] = bisect_right(times, snapshot["at_s"]) - 1
        checkpoint["state_hash"] = sha256_hex(state)
        state["checkpoint"] = checkpoint
