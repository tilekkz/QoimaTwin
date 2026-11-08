"""Identity, actual event order and captured-state anchors for connected flow artifacts."""

from bisect import bisect_right
from typing import Any

from app.storage.canonical_json import sha256_hex
from app.v3.execution_types import ACTOR_IDS
from app.v3.flow_run_schema import validate_schema
from app.v3.flow_run_stock import StockAudit, check_metric_counts
from app.v3.light_flow_models import LIGHT_FLOW_ENGINE_VERSION


def run_identity(input_hash: str) -> str:
    return sha256_hex({"engine_version": LIGHT_FLOW_ENGINE_VERSION, "input_hash": input_hash})


def validate_flow_run(value: dict[str, Any]) -> None:
    validate_schema(value)
    if value["engine_version"] != LIGHT_FLOW_ENGINE_VERSION or value["run_id"] != run_identity(
        value["input_hash"]
    ):
        raise ValueError("Connected flow run identity mismatch")
    horizon, end = value["horizon_tick"], value["observed_until_tick"]
    if not 0 < horizon <= value["end_tick_limit"] or not 0 <= end <= value["end_tick_limit"]:
        raise ValueError("Invalid connected flow boundaries")
    if value["source_revision"] != value["catalog"]["source_revision"]:
        raise ValueError("Connected flow source identity mismatch")
    _events(value)
    stock_audit = StockAudit(value["catalog"])
    for event in value["events"]:
        if event["delta"]:
            stock_audit.delta(event["delta"])
    checkpoints = value["checkpoints"]
    ticks = [c["tick"] for c in checkpoints]
    expected = {0, horizon, end, *range(0, end + 1, 30_000_000)}
    if ticks != sorted(expected):
        raise ValueError("Captured checkpoints must include cadence and exact H/end")
    for checkpoint in checkpoints:
        _checkpoint(value, checkpoint)
        stock_audit.check(checkpoint["state"])
    check_metric_counts(value)
    validate_terminal_status(value)
    for key, tick in (("at_horizon", horizon), ("at_end", end)):
        if value[key] != next(c for c in checkpoints if c["tick"] == tick):
            raise ValueError("H/end differs from its captured checkpoint")
    if (
        value["metrics"]["at_horizon"]["tick"] != horizon
        or value["metrics"]["at_end"]["tick"] != end
    ):
        raise ValueError("Metrics observation differs from captured boundary")


def validate_terminal_status(run: dict[str, Any]) -> None:
    state = run["at_end"]["state"]
    complete = (
        all(o["shipped_tick"] is not None for o in state["orders"])
        and all(
            w["order_id"] is None and w["operation"] is None and w["waiting_since"] is None
            for w in state["workers"]
        )
        and state["cart"]["order_id"] is None
        and state["cart"]["operation"] is None
        and not state["leases"]
        and not state["belt"]["leases"]
        and all(
            c["status"] == "complete" and c["motion"] is None and not c["occupied_cells"]
            for c in state["belt"]["carriers"]
        )
    )
    if run["status"] != ("complete" if complete else "partial"):
        raise ValueError("connected status differs from actual operational state")


def _events(run: dict[str, Any]) -> None:
    events = run["events"]
    ticks = [e["tick"] for e in events]
    if ticks != sorted(ticks) or any(t > run["observed_until_tick"] for t in ticks):
        raise ValueError("Events exceed actual observed order/time")
    for seq, event in enumerate(events):
        if event["seq"] != seq:
            raise ValueError("Events require contiguous stable sequence")
        operation = event["operation"]
        if (
            operation
            and event["kind"] == "operation_completed"
            and operation["planned_end_tick"] != event["tick"]
        ):
            raise ValueError("Completion is not an actual observed operation end")
        if event["belt_event"] and event["belt_event"]["tick"] != event["tick"]:
            raise ValueError("Embedded belt event has a different clock")


def _checkpoint(run: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    state, tick = checkpoint["state"], checkpoint["tick"]
    expected = bisect_right([e["tick"] for e in run["events"]], tick) - 1
    if checkpoint["last_seq"] != expected or checkpoint["state_hash"] != sha256_hex(state):
        raise ValueError("Checkpoint hash or inclusive event watermark mismatch")
    if state["belt"]["tick"] != tick:
        raise ValueError("Belt observation clock mismatch")
    workers = state["workers"]
    if len(workers) != 24 or {w["actor_id"] for w in workers} != set(ACTOR_IDS):
        raise ValueError("Checkpoint does not retain all actor identities")
    for row in [*workers, state["cart"]]:
        operation = row["operation"]
        if operation and not operation["start_tick"] <= tick < operation["planned_end_tick"]:
            raise ValueError("Captured open operation is outside its actual interval")
    for carrier in state["belt"]["carriers"]:
        motion = carrier["motion"]
        if motion and not motion["start_tick"] <= tick < motion["planned_end_tick"]:
            raise ValueError("Captured open belt motion is outside its actual interval")
    _stock(run["catalog"], state["stock"])


def _stock(catalog: dict[str, Any], stock: dict[str, Any]) -> None:
    containers = {c["container_id"] for c in catalog["containers"]}
    owners = {o["owner_id"] for o in catalog["owners"]}
    units = {u["unit_id"] for u in catalog["units"]}
    rows, locations = stock["containers"], stock["locations"]
    if len(rows) != len(containers) or {r["container_id"] for r in rows} != containers:
        raise ValueError("Captured physical container catalog differs")
    if any(r["owner_id"] not in owners for r in rows):
        raise ValueError("Captured owner is absent from immutable catalog")
    if len(locations) != len(units) or {r["unit_id"] for r in locations} != units:
        raise ValueError("Captured source unit conservation differs")
    if any(r["container_id"] not in containers for r in locations):
        raise ValueError("Captured unit is assigned to an unknown container")
