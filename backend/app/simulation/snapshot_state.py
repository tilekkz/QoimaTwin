"""Mutable engine state as plain JSON for replay snapshots (05 §10 item 3, ADR 0010).

Only mutable state is captured: actors, cargo and cells, ledger balances and claims, queues, the
tote pool, stations, pallets, merge cursors and pending timers. Immutable inputs (layout, catalog,
orders, receipts) and the event/action history are referenced, never copied; the active action of
each actor is embedded so a seek does not need earlier chunks. Every list is sorted or kept in its
engine order, so equal states give equal canonical bytes.

Two pieces of state live only inside scheduled callbacks and are reconstructed here from records:
the pallet on the outbound forklift (from `pallet_sealed`/`order_dispatched` events) and each
actor's current activity (from its action intervals). See ADR 0010.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from app.inventory.ledger import Holding, Ledger
from app.simulation.recorder import Action, Event, Vec3
from app.simulation.scheduler import PhaseScheduler
from app.simulation.shipping import Pallet, PalletState

if TYPE_CHECKING:
    from app.simulation.engine import Engine

Json = dict[str, Any]
COUNTED_KINDS = {
    "order_arrived": "arrived",
    "order_rejected_inventory": "rejected",
    "order_packed": "packed",
    "order_dispatched": "dispatched",
    "receipt_accepted": "accepted",
    "pallet_putaway": "putaway",
}


class ActionTracker:
    """Per actor: the action covering a boundary and the last finished one (amortised O(1))."""

    def __init__(self) -> None:
        self._cursor = 0
        self._pending: dict[str, deque[Action]] = {}
        self.last_done: dict[str, Action] = {}

    def advance(self, actions: list[Action], at_tick: int) -> None:
        for action in actions[self._cursor :]:
            self._pending.setdefault(action.actor_id, deque()).append(action)
        self._cursor = len(actions)
        for actor_id, queue in self._pending.items():
            while queue and queue[0].end_tick <= at_tick:
                self.last_done[actor_id] = queue.popleft()

    def active(self, actor_id: str, at_tick: int) -> Action | None:
        queue = self._pending.get(actor_id)
        if queue and queue[0].start_tick <= at_tick:
            return queue[0]
        return None


class EventIndex:
    """Running counters and the parcels of sealed, not yet dispatched pallets."""

    def __init__(self) -> None:
        self._cursor = 0
        self.counts: Counter[str] = Counter()
        self.sealed: dict[str, list[str]] = {}

    def advance(self, events: list[Event]) -> None:
        for event in events[self._cursor :]:
            if event.kind in COUNTED_KINDS:
                self.counts[COUNTED_KINDS[event.kind]] += 1
            if event.kind == "pallet_sealed":
                self.sealed[event.entity_id] = list(event.payload["parcel_ids"])
            elif event.kind == "order_dispatched":
                self.sealed.pop(event.payload["pallet_id"], None)
        self._cursor = len(events)


class StateCapture:
    """Callable `at_tick -> state` for the checkpointer; call it at non-decreasing ticks."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.actions = ActionTracker()
        self.events = EventIndex()

    def __call__(self, at_tick: int) -> Json:
        engine = self.engine
        ctx = engine.ctx
        self.actions.advance(ctx.recorder.actions, at_tick)
        self.events.advance(ctx.recorder.events)
        return {
            "actors": self._actors(at_tick),
            "conveyor": conveyor_state(engine),
            "ledger": ledger_state(ctx.ledger),
            "orders": self._orders(),
            "totes": {
                "free": sorted(engine.picking.free_totes),
                "allocated": sorted(engine.picking.allocated_totes),
            },
            "stations": stations_state(engine),
            "shipping": self._shipping(at_tick),
            "receiving": self._receiving(),
            "timers": timers_state(ctx.sched),
        }

    def _actors(self, at_tick: int) -> list[Json]:
        busy = busy_actors(self.engine)
        result = []
        for actor in sorted(self.engine.ctx.inputs.actors.actors, key=lambda a: a.actor_id):
            active = self.actions.active(actor.actor_id, at_tick)
            if active is not None:
                state = str(active.state)
                pos = _pos(active.pos) if active.pos is not None else None
            else:
                state = "BLOCKED" if actor.actor_id in busy else "IDLE"
                last = self.actions.last_done.get(actor.actor_id)
                pos = _pos(_end_pos(last) if last is not None else actor.initial_pos)
            result.append(
                {
                    "actor_id": actor.actor_id,
                    "role": actor.role,
                    "state": state,
                    "pos": pos,
                    "action": action_json(active) if active is not None else None,
                }
            )
        return result

    def _orders(self) -> Json:
        picking = self.engine.picking
        counts = self.events.counts
        return {
            "queue": [order.order_id for order in picking.queue],
            "picking": [
                {"order_id": oid, "actor_id": job.picker.actor_id, "tote_id": job.tote_id}
                for oid, job in sorted(picking.jobs.items())
            ],
            "counts": {k: counts[k] for k in ("arrived", "rejected", "packed", "dispatched")},
            "status": order_status(self.engine),
        }

    def _shipping(self, at_tick: int) -> Json:
        engine = self.engine
        shipping, outbound = engine.shipping, engine.outbound
        age = engine.ctx.ticks(engine.ctx.config.pallet_max_age_s)
        scanning = []
        for shipper in shipping.shippers:
            action = self.actions.active(shipper.actor_id, at_tick) if shipper.busy else None
            if action is not None:
                scan = {"actor_id": shipper.actor_id, "order_id": action.entity_id}
                scanning.append({**scan, "until_tick": action.end_tick})
        open_pallet = shipping.open_pallet
        return {
            "buffer": [parcel.cargo_id for parcel in shipping.buffer],
            "open_pallet": pallet_json(open_pallet, age) if open_pallet is not None else None,
            "sealed_queue": [pallet_json(p, age) for p in shipping.sealed_queue],
            "scanning": scanning,
            "outbound": {
                "busy": outbound.busy,
                "tasks": [p.pallet_id for p in outbound.tasks],
                "carrying": self._carried_pallet(),
            },
        }

    def _carried_pallet(self) -> Json | None:
        shipping = self.engine.shipping
        parked = {p.pallet_id for p in shipping.sealed_queue}
        carried = sorted(pid for pid in self.events.sealed if pid not in parked)
        if len(carried) > 1:
            raise RuntimeError(f"more than one pallet on the outbound forklift: {carried}")
        if not carried:
            return None
        pallet_id = carried[0]
        parcels = self.events.sealed[pallet_id]
        return {"pallet_id": pallet_id, "state": str(PalletState.CLAIMED), "parcels": parcels}

    def _receiving(self) -> Json:
        receiving = self.engine.receiving
        counts = self.events.counts
        return {
            "external": [r.receipt_id for r in receiving.external],
            "area": [
                {
                    "pallet_id": p.pallet_id,
                    "receipt_id": p.receipt.receipt_id,
                    "state": str(p.state),
                }
                for p in receiving.area
            ],
            "forklift_busy": receiving.forklift_busy,
            "staging_used": receiving.staging_used,
            "counts": {k: counts[k] for k in ("accepted", "putaway")},
        }


def busy_actors(engine: Engine) -> set[str]:
    """Actors that hold work in domain state; without a current action they are BLOCKED."""
    busy = {p.actor_id for p in engine.picking.pickers if p.busy}
    busy |= {
        s.packer_id
        for s in engine.packing.stations.values()
        if s.in_service is not None or s.blocked_parcel is not None
    }
    busy |= {s.actor_id for s in engine.shipping.shippers if s.busy}
    busy |= {r.actor_id for r in engine.receiving.receivers if r.busy}
    if engine.outbound.busy:
        busy.add(engine.outbound.driver_id)
    if engine.receiving.forklift_busy:
        busy.add(engine.receiving.driver_id)
    return busy


def conveyor_state(engine: Engine) -> Json:
    conveyor = engine.conveyor
    requests = sorted(conveyor.requests, key=lambda r: (r.inlet, r.sort_key, r.cargo_id))
    return {
        "cells": [[cell, cargo] for cell, cargo in sorted(conveyor.occupancy.items())],
        "cargo": [
            {"cargo_id": c.cargo_id, "kind": c.kind, "order_id": c.order_id, "target": c.target}
            for _, c in sorted(conveyor.cargo.items())
        ],
        "admissions": [
            {
                "inlet": r.inlet,
                "cargo_id": r.cargo_id,
                "ready_tick": r.sort_key[0],
                "owner": r.sort_key[1],
            }
            for r in requests
        ],
        "merge_cursors": [[cell, cursor] for cell, cursor in sorted(conveyor.cursors.items())],
    }


def _holding(holding: Holding) -> list[Any]:
    loc = holding.location
    return [holding.sku_id, holding.lot_id, str(loc.kind), loc.ref]


def ledger_state(ledger: Ledger) -> Json:
    """Balances, reservations and per-order claims; reads the ledger's private maps read-only."""
    claims = [
        [order_id, *_holding(h), q]
        for order_id, lines in sorted(ledger._order_claims.items())
        for h, q in sorted(lines.items())
    ]
    return {
        "balances": [[*_holding(h), q] for h, q in sorted(ledger._balances.items())],
        "reservations": [[*_holding(h), q] for h, q in sorted(ledger._reserved.items())],
        "claims": claims,
        "accepted": [[sku, q] for sku, q in sorted(ledger._accepted.items())],
    }


def stations_state(engine: Engine) -> list[Json]:
    return [
        {
            "pack_id": s.pack_id,
            "waiting": [tote.cargo_id for tote in s.waiting],
            "in_service": s.in_service.cargo_id if s.in_service is not None else None,
            "cargo": [asdict(c) for c in s.waiting]
            + ([asdict(s.in_service)] if s.in_service is not None else []),
            "blocked_parcel": s.blocked_parcel,
            "blocked_since": s.blocked_since if s.blocked_parcel is not None else None,
            "reserved_wip": s.reserved_wip,
        }
        for s in engine.packing.stations.values()
    ]


def order_status(engine: Engine) -> dict[str, str]:
    """Current status only, without copying per-order milestone history."""
    queued = {order.order_id for order in engine.picking.queue}
    result = {}
    for oid, record in sorted(engine.metrics.orders.items()):
        if record.dispatched is not None:
            result[oid] = "dispatched"
        elif record.rejected is not None:
            result[oid] = "unfulfilled_inventory"
        elif record.packed is not None:
            result[oid] = "packed"
        else:
            result[oid] = "queued" if oid in queued else "admitted"
    return result


def pallet_json(pallet: Pallet, max_age_ticks: int) -> Json:
    first = pallet.first_placement
    timed = first is not None and pallet.state is PalletState.OPEN
    return {
        "pallet_id": pallet.pallet_id,
        "state": str(pallet.state),
        "parcels": [parcel.cargo_id for parcel in pallet.parcels],
        "reserved": pallet.reserved,
        "first_placement_tick": first,
        "generation": pallet.generation,
        "expires_tick": first + max_age_ticks if timed and first is not None else None,
    }


def timers_state(sched: PhaseScheduler) -> list[Json]:
    """Pending scheduler descriptors (callbacks are not serializable; see ADR 0010)."""
    items = [i for bucket in sched._buckets.values() for i in bucket.items if not i.cancelled]
    return [
        {
            "tick": i.tick,
            "phase": int(i.phase),
            "rank": i.rank,
            "key": list(i.key),
            "seq": i.seq,
            "unique": str(i.unique) if i.unique is not None else None,
        }
        for i in sorted(items, key=lambda i: (i.tick, int(i.phase), i.seq))
    ]


def action_json(action: Action) -> Json:
    return {
        "action_id": action.action_id,
        "state": str(action.state),
        "operation": action.operation,
        "entity_id": action.entity_id,
        "start_tick": action.start_tick,
        "end_tick": action.end_tick,
        "pos": _pos(action.pos) if action.pos is not None else None,
        "waypoints": [[w.node_id, _pos(w.pos), w.at_tick] for w in action.waypoints],
    }


def _end_pos(action: Action) -> Vec3:
    if action.waypoints:
        return action.waypoints[-1].pos
    if action.pos is None:
        raise RuntimeError(f"{action.action_id}: stationary action has no position")
    return action.pos


def _pos(pos: Vec3) -> list[float]:
    return [float(v) for v in pos]
