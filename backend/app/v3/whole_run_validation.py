"""Validate one shared inventory/actor journal and the captured inclusive H/end boundaries."""

from bisect import bisect_right

from app.storage.canonical_json import sha256_hex
from app.v3.execution_types import ACTOR_IDS
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.interface import Json
from app.v3.receipt_run_journal import InventoryJournal, same
from app.v3.receipt_run_operations import validate_handoff
from app.v3.receipt_run_validation import _credit_event, _events
from app.v3.whole_flow_models import WHOLE_FLOW_ENGINE_VERSION
from app.v3.whole_flow_validate import validate_whole_flow
from app.v3.whole_run_context import profile_from_catalog
from app.v3.whole_run_custody import check_custody, guard_delta
from app.v3.whole_run_facts import WholeFacts
from app.v3.whole_run_metrics import summary
from app.v3.whole_run_operations import WholeOperations
from app.v3.whole_run_schema import PUBLICATION_VERSION, validate_schema


def run_identity(input_hash: str) -> str:
    return sha256_hex(
        {
            "engine_version": WHOLE_FLOW_ENGINE_VERSION,
            "publication_version": PUBLICATION_VERSION,
            "input_hash": input_hash,
        }
    )


def validate_whole_run(run: Json) -> None:
    validate_schema(run)
    try:
        _validate(run)
    except (KeyError, IndexError, TypeError, StopIteration) as exc:
        raise ValueError("Whole publication has an invalid physical reference") from exc


def _boundaries(run: Json) -> None:
    horizon, end, cap = (run[k] for k in ("horizon_tick", "observed_until_tick", "end_tick_limit"))
    if (
        any(type(t) is not int for t in (horizon, end, cap))
        or not 0 < horizon <= cap
        or not 0 <= end <= cap
    ):
        raise ValueError("Invalid whole observation boundary")
    if run["engine_version"] != WHOLE_FLOW_ENGINE_VERSION or run["run_id"] != run_identity(
        run["input_hash"]
    ):
        raise ValueError("Whole native identity mismatch")
    same(run["source_revision"], run["catalog"]["source_revision"], "Whole source identity differs")
    expected = sorted({0, horizon, end, *range(0, end + 1, 30_000_000)})
    same([p["tick"] for p in run["checkpoints"]], expected, "Whole captured cadence differs")


def _validate(run: Json) -> None:
    _boundaries(run)
    events, catalog = run["events"], run["catalog"]
    _events(events, run["observed_until_tick"])
    _transactions(events)
    profile = profile_from_catalog(catalog)
    _, conveyor, _ = _pinned_reference()
    validate_whole_flow(profile, conveyor)
    inventory = InventoryJournal(catalog)
    facts = WholeFacts(catalog, events, inventory)
    operations = WholeOperations(profile, inventory)
    ticks, cursor = [e["tick"] for e in events], 0
    for point in run["checkpoints"]:
        while cursor < len(events) and events[cursor]["tick"] <= point["tick"]:
            event = events[cursor]
            _credit_event(run, event, events)
            validate_handoff(catalog, event, events)
            operations.apply(event, run["horizon_tick"])
            guard_delta(event, facts, operations)
            inventory.apply(event)
            facts.apply(event)
            facts.check_claims()
            facts.check_shipped_capacity()
            cursor += 1
        _checkpoint(point, bisect_right(ticks, point["tick"]) - 1, inventory, facts, operations)
    for name, tick in (("at_horizon", run["horizon_tick"]), ("at_end", run["observed_until_tick"])):
        same(
            run[name],
            next(p for p in run["checkpoints"] if p["tick"] == tick),
            "Whole H/end differs from its actual captured state",
        )
    same(run["metrics"], summary(run), "Whole business or once-counted common labor metrics differ")
    _terminal(run)


def _transactions(events: list[Json]) -> None:
    identities: set[str] = set()
    for event in events:
        delta = event["delta"]
        if delta is None:
            continue
        identity = delta["transaction_id"]
        if identity in identities:
            raise ValueError("Atomic stock transaction identity was reused")
        identities.add(identity)


def _checkpoint(
    point: Json,
    last_seq: int,
    inventory: InventoryJournal,
    facts: WholeFacts,
    operations: WholeOperations,
) -> None:
    state, tick = point["state"], point["tick"]
    same(point["last_seq"], last_seq, "Whole checkpoint watermark differs")
    if point["state_hash"] != sha256_hex(state) or state["belt"]["tick"] != tick:
        raise ValueError("Whole checkpoint hash/clock differs")
    workers = state["workers"]
    if len(workers) != 24 or {w["actor_id"] for w in workers} != set(ACTOR_IDS):
        raise ValueError("Whole captured state loses the actual shared 24 actors")
    for actor in [*workers, state["cart"]]:
        op = actor["operation"]
        if op and not op["start_tick"] <= tick < op["planned_end_tick"]:
            raise ValueError("Captured actor operation is not actually open")
    inventory.check(state)
    facts.check(state, tick)
    operations.check(state, tick)
    check_custody(state, facts, inventory)


def _terminal(run: Json) -> None:
    state = run["at_end"]["state"]
    excluded = {
        r["definition"]["receipt_id"]
        for r in run["catalog"]["declared_receipts"]
        if r["arrival_tick"] >= run["horizon_tick"]
    }
    complete = (
        all(o["shipped_tick"] is not None for o in state["orders"])
        and all(o["returned_tick"] is not None for o in state["whole_orders"])
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
        raise ValueError("Whole terminal status omits paid return or outstanding shared resources")
