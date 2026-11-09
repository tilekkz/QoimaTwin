"""Source-bound manual execution export, separate from V2 and static V3 artifacts."""

from copy import deepcopy
from functools import lru_cache

from jsonschema import Draft202012Validator, ValidationError

from app.storage.canonical_json import sha256_hex
from app.v3.execution_types import (
    MANUAL_ENGINE_VERSION,
    BoundGraph,
    ExecutionProfile,
    ManualOutcome,
)
from app.v3.interface import Json
from app.v3.manual_metrics import summary
from app.v3.run_decode import outcome_from_wire, profile_from_wire
from app.v3.run_event_validation import validate_events
from app.v3.run_profile_validation import validate_profile_wire
from app.v3.run_replay import apply_event, initial_state, settle
from app.v3.run_schema import schema
from app.v3.run_trace import active_operation_ids, operation_index
from app.v3.run_values import record
from app.v3.runtime_graph_source import compiled_graph
from app.v3.runtime_time import DURATION_ROUNDING, TICKS_PER_SECOND


def build_manual_run(
    profile: ExecutionProfile,
    bound_graph: BoundGraph,
    outcome: ManualOutcome,
    *,
    graph_document: Json,
    end_tick_limit: int,
    snapshot_interval_ticks: int = 30_000_000,
) -> Json:
    _graph_binding(profile, bound_graph, graph_document)
    if outcome.profile_id != profile.profile_id:
        raise ValueError("manual outcome profile binding mismatch")
    if type(snapshot_interval_ticks) is not int or snapshot_interval_ticks <= 0:
        raise ValueError("manual snapshot interval must be positive integer ticks")
    value = _envelope(profile, outcome, graph_document, end_tick_limit)
    value["initial_state"] = initial_state(value["profile"])
    value["operations"] = operation_index(value)
    value["metrics"] = summary(profile, outcome)
    value["run_id"] = run_identity(value)
    value["snapshots"] = _snapshots(value, snapshot_interval_ticks)
    validate_manual_run(value)
    return value


def _envelope(profile: ExecutionProfile, outcome: ManualOutcome, graph: Json, cap: int) -> Json:
    return {
        "schema_id": "qoima.manual-run.v3-proposal",
        "schema_version": "0.1.0",
        "contract_status": "proposal",
        "data_kind": "manual_execution_proposal",
        "source_label": "actual_engine_run",
        "engine_version": MANUAL_ENGINE_VERSION,
        "profile": record(profile),
        "graph_document": deepcopy(graph),
        "clock": {"ticks_per_second": TICKS_PER_SECOND, "duration_rounding": DURATION_ROUNDING},
        "capabilities": {
            "actual_engine_run": True,
            "frontend_adapter": False,
            "full_v3_warehouse": False,
        },
        "end_tick_limit": cap,
        "observed_until_tick": max(outcome.at_horizon.tick, outcome.at_end.tick),
        "at_horizon": record(outcome.at_horizon),
        "at_end": record(outcome.at_end),
        "events": [record(event) for event in outcome.events],
    }


def _graph_binding(profile: ExecutionProfile, bound: BoundGraph, document: Json) -> None:
    if not document.get("connector_provenance"):
        raise ValueError("manual augmented graph lacks connector provenance")
    if sha256_hex(document) != bound.sha256 or bound.sha256 != profile.graph_sha256:
        raise ValueError("manual graph content hash mismatch")
    if (
        profile.layout_version != bound.layout_version
        or document["layout_version"] != bound.layout_version
    ):
        raise ValueError("manual graph layout binding mismatch")
    actual = compiled_graph(document, "walk")
    if actual.node_ids != bound.graph.node_ids or actual.arcs != bound.graph.arcs:
        raise ValueError("manual augmented graph differs from the runtime graph")


def run_identity(value: Json) -> str:
    return sha256_hex(
        {
            key: value[key]
            for key in (
                "schema_id",
                "schema_version",
                "engine_version",
                "profile",
                "clock",
                "end_tick_limit",
            )
        }
        | {"horizon_tick": value["at_horizon"]["tick"]}
    )


def _snapshots(value: Json, interval: int) -> list[Json]:
    until = value["observed_until_tick"]
    boundaries = sorted(
        {
            0,
            until,
            value["at_horizon"]["tick"],
            value["at_end"]["tick"],
            *range(0, until + 1, interval),
        }
    )
    state, through, result = deepcopy(value["initial_state"]), -1, []
    for tick in boundaries:
        while through + 1 < len(value["events"]) and value["events"][through + 1]["tick"] <= tick:
            through += 1
            apply_event(state, value["events"][through])
        settle(state, value["profile"], tick)
        result.append(
            {
                "tick": tick,
                "through_seq": through,
                "state_hash": sha256_hex(state),
                "state": deepcopy(state),
                "active_operation_ids": active_operation_ids(value["operations"], tick),
            }
        )
    return result


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    value = schema()
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def validate_manual_run(value: Json) -> None:
    try:
        _validator().validate(value)
    except ValidationError as exc:
        raise ValueError(f"manual run schema: {exc.json_path}: {exc.message}") from exc
    if value["run_id"] != run_identity(value):
        raise ValueError("manual run identity mismatch")
    profile = value["profile"]
    if sha256_hex(value["graph_document"]) != profile["graph_sha256"]:
        raise ValueError("manual graph content hash mismatch")
    if value["initial_state"] != initial_state(profile):
        raise ValueError("manual initial state differs from the frozen profile")
    graph = compiled_graph(value["graph_document"], "walk")
    validate_profile_wire(value, graph)
    validate_events(value, graph)
    if value["operations"] != operation_index(value):
        raise ValueError("manual operations differ from actual observed event intervals")
    if value["metrics"] != summary(profile_from_wire(profile), outcome_from_wire(value)):
        raise ValueError("manual metrics differ from actual business/resource observations")
    _check_observations(value)


def _check_observations(value: Json) -> None:
    until = max(value["at_horizon"]["tick"], value["at_end"]["tick"])
    if until != value["observed_until_tick"] or until > value["end_tick_limit"]:
        raise ValueError("manual observation exceeds the requested end cap")
    state, previous = deepcopy(value["initial_state"]), 0
    for seq, event in enumerate(value["events"]):
        if event["seq"] != seq or not previous <= event["tick"] <= value["at_end"]["tick"]:
            raise ValueError("manual events must be ordered, contiguous and observed")
        previous = event["tick"]
    expected = {row["tick"]: row for row in value["snapshots"]}
    if len(expected) != len(value["snapshots"]):
        raise ValueError("manual snapshots have duplicate boundaries")
    if 0 not in expected or any(tick > until for tick in expected):
        raise ValueError("manual snapshot boundary is outside the observed timeline")
    through = -1
    for tick, row in sorted(expected.items()):
        while through + 1 < len(value["events"]) and value["events"][through + 1]["tick"] <= tick:
            through += 1
            apply_event(state, value["events"][through])
        settle(state, value["profile"], tick)
        if row != {
            "tick": tick,
            "through_seq": through,
            "state_hash": sha256_hex(state),
            "state": state,
            "active_operation_ids": active_operation_ids(value["operations"], tick),
        }:
            raise ValueError("manual snapshot differs from typed event replay")
    for name in ("at_horizon", "at_end"):
        state = expected.get(value[name]["tick"], {}).get("state")
        if state != value[name]:
            raise ValueError(f"manual {name} differs from typed event replay")
