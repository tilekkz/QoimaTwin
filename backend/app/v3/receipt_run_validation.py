"""Strict captured receipt state, actual inventory journal and operational boundaries."""

from bisect import bisect_right

from app.storage.canonical_json import sha256_hex
from app.v3.execution_types import ACTOR_IDS
from app.v3.flow_run_stock import check_metric_counts
from app.v3.interface import Json
from app.v3.receipt_flow_models import RECEIPT_FLOW_ENGINE_VERSION
from app.v3.receipt_run_facts import ReceiptFacts
from app.v3.receipt_run_journal import InventoryJournal, same
from app.v3.receipt_run_operations import completed_operation, validate_handoff
from app.v3.receipt_run_schema import PUBLICATION_VERSION, validate_schema


def run_identity(input_hash: str) -> str:
    return sha256_hex(
        {
            "engine_version": RECEIPT_FLOW_ENGINE_VERSION,
            "publication_version": PUBLICATION_VERSION,
            "input_hash": input_hash,
        }
    )


def validate_receipt_run(run: Json) -> None:
    validate_schema(run)
    try:
        _validate(run)
    except (KeyError, IndexError, TypeError, StopIteration) as exc:
        raise ValueError("Receipt publication contains an invalid physical reference") from exc


def _validate(run: Json) -> None:
    horizon, end, cap = (run[k] for k in ("horizon_tick", "observed_until_tick", "end_tick_limit"))
    if (
        any(type(t) is not int for t in (horizon, end, cap))
        or not 0 < horizon <= cap
        or not 0 <= end <= cap
    ):
        raise ValueError("Invalid receipt observation boundary")
    if run["engine_version"] != RECEIPT_FLOW_ENGINE_VERSION or run["run_id"] != run_identity(
        run["input_hash"]
    ):
        raise ValueError("Receipt native identity mismatch")
    same(
        run["source_revision"], run["catalog"]["source_revision"], "Receipt source identity differs"
    )
    events = run["events"]
    _events(events, end)
    inventory = InventoryJournal(run["catalog"])
    facts = ReceiptFacts(run["catalog"], events, inventory)
    ticks = [e["tick"] for e in events]
    captures = run["checkpoints"]
    expected = sorted({0, horizon, end, *range(0, end + 1, 30_000_000)})
    same([c["tick"] for c in captures], expected, "Receipt captured cadence differs")
    cursor = 0
    for point in captures:
        while cursor < len(events) and events[cursor]["tick"] <= point["tick"]:
            _credit_event(run, events[cursor], events)
            validate_handoff(run["catalog"], events[cursor], events)
            inventory.apply(events[cursor])
            facts.apply(events[cursor])
            facts.check_claims()
            cursor += 1
        _checkpoint(point, bisect_right(ticks, point["tick"]) - 1, inventory, facts)
    for name, tick in (("at_horizon", horizon), ("at_end", end)):
        point = next(c for c in captures if c["tick"] == tick)
        same(run[name], point, "Receipt H/end differs from captured observation")
        same(
            run["receipt_metrics"][name],
            receipt_counts(point, run["catalog"]),
            "Receipt metrics differ",
        )
    check_metric_counts(run)
    _terminal(run)


def _events(events: list[Json], end: int) -> None:
    previous = -1
    for seq, event in enumerate(events):
        if type(event["seq"]) is not int or event["seq"] != seq:
            raise ValueError("Receipt events require exact contiguous sequence")
        tick = event["tick"]
        if type(tick) is not int or not previous <= tick <= end:
            raise ValueError("Receipt events exceed actual ordered observation")
        previous = tick
        operation = event["operation"]
        if (
            operation is not None
            and event["kind"] == "operation_completed"
            and operation["planned_end_tick"] != tick
        ):
            raise ValueError("Receipt event invents future operation completion")
        if event["belt_event"] is not None and event["belt_event"]["tick"] != tick:
            raise ValueError("Receipt embedded belt clock differs")


def _credit_event(run: Json, event: Json, events: list[Json]) -> None:
    if event["delta"] is None or event["delta"]["delta_type"] != "receipt_creation":
        return
    key, tick = event["order_id"], event["tick"]
    offer = next(
        r for r in run["catalog"]["declared_receipts"] if r["definition"]["receipt_id"] == key
    )
    port = next(
        p for p in run["catalog"]["receipt_process"]["ports"] if p["port_id"] == offer["port_id"]
    )
    operation = completed_operation(event, events, "receipt_service")
    if event["actor_id"] not in port["receiver_ids"]:
        raise ValueError("Receipt credit lacks actual eligible service completion")
    start = operation["start_tick"]
    if operation["target_node"] != port["node_id"] or tick - start != port["service_tick"]:
        raise ValueError("Receipt credit service duration/place differs")
    if not offer["arrival_tick"] <= start or not any(
        a <= start < min(b, run["horizon_tick"]) and tick <= min(b, run["horizon_tick"])
        for a, b in port["windows"]
    ):
        raise ValueError("Receipt credit is outside its actual service admission window")


def _checkpoint(
    point: Json, last_seq: int, inventory: InventoryJournal, facts: ReceiptFacts
) -> None:
    state, tick = point["state"], point["tick"]
    same(point["last_seq"], last_seq, "Receipt checkpoint watermark differs")
    if point["state_hash"] != sha256_hex(state) or state["belt"]["tick"] != tick:
        raise ValueError("Receipt checkpoint hash/clock differs")
    workers = state["workers"]
    if len(workers) != 24 or {w["actor_id"] for w in workers} != set(ACTOR_IDS):
        raise ValueError("Receipt checkpoint loses the actual 24 actors")
    for actor in [*workers, state["cart"]]:
        op = actor["operation"]
        if op and not op["start_tick"] <= tick < op["planned_end_tick"]:
            raise ValueError("Receipt captured operation is not actually open")
    for carrier in state["belt"]["carriers"]:
        motion = carrier["motion"]
        if motion and not motion["start_tick"] <= tick < motion["planned_end_tick"]:
            raise ValueError("Receipt captured belt motion is not actually open")
    inventory.check(state)
    facts.check(state, tick)
    _custody(state, tick, inventory)


def _custody(state: Json, tick: int, inventory: InventoryJournal) -> None:
    for view in state["receipts"]:
        key = view["receipt_id"]
        offer = inventory.offers[key]
        times = [
            view[k]
            for k in ("admitted_tick", "credited_tick", "placed_tick", "returned_tick")
            if view[k] is not None
        ]
        if any(
            type(t) is not int or not offer["arrival_tick"] <= t <= tick for t in times
        ) or times != sorted(times):
            raise ValueError("Receipt transition lies outside actual observed chronology")
        credited = view["credited_tick"] is not None
        if credited != (key in inventory.registered):
            raise ValueError("Receipt credited state differs from actually existing stock")
        if not credited:
            continue
        owner = (
            offer["slot_owner_id"]
            if view["placed_tick"] is not None
            else (
                view["buffer_owner_id"]
                if view["status"] == "buffered"
                else "actor:" + str(view["actor_id"])
            )
        )
        if inventory.containers[offer["definition"]["hu_id"]]["owner_id"] != owner:
            raise ValueError("Receipt physical custody differs from its completed stage")
        claim = next(
            (c for c in state["inventory"]["claims"] if c["claim_id"] == "receipt:" + key), None
        )
        if (claim is not None) != (view["placed_tick"] is None):
            raise ValueError("Receipt whole-HU claim does not persist until putaway")


def receipt_counts(point: Json, catalog: Json) -> Json:
    rows = point["state"]["receipts"]
    arrived = sum(r["status"] != "unreleased" for r in rows)
    credited = sum(r["credited_tick"] is not None for r in rows)
    putaway = sum(r["placed_tick"] is not None for r in rows)
    returned = sum(r["returned_tick"] is not None for r in rows)
    quantities = {
        r["definition"]["receipt_id"]: r["definition"]["quantity_units"]
        for r in catalog["declared_receipts"]
    }
    return {
        "tick": point["tick"],
        "arrived_receipts": arrived,
        "credited_receipts": credited,
        "credited_units": sum(
            quantities[r["receipt_id"]] for r in rows if r["credited_tick"] is not None
        ),
        "putaway_receipts": putaway,
        "returned_receipts": returned,
        "pending_putaway": arrived - putaway,
        "pending_return": arrived - returned,
        "receiver_resource_ticks": sum(r["paid_exposure_ticks"] for r in rows),
    }


def _terminal(run: Json) -> None:
    state = run["at_end"]["state"]
    excluded = {
        r["definition"]["receipt_id"]
        for r in run["catalog"]["declared_receipts"]
        if r["arrival_tick"] >= run["horizon_tick"]
    }
    complete = (
        all(o["shipped_tick"] is not None for o in state["orders"])
        and all(
            r["returned_tick"] is not None or r["receipt_id"] in excluded for r in state["receipts"]
        )
        and all(
            w["order_id"] is None and w["operation"] is None and w["waiting_since"] is None
            for w in state["workers"]
        )
        and state["cart"]["order_id"] is None
        and state["cart"]["operation"] is None
        and not state["leases"]
        and not state["inventory"]["claims"]
        and not state["belt"]["leases"]
        and all(
            c["status"] == "complete" and c["motion"] is None and not c["occupied_cells"]
            for c in state["belt"]["carriers"]
        )
    )
    if run["status"] != ("complete" if complete else "partial"):
        raise ValueError("Receipt terminal status disagrees with paid return or open resources")
