"""Observed N1 differences use common paid labor once and retain raw completion boundaries."""

from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_metrics_values import integer
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_pair_report import event_hash, observation_hash
from app.v3.flow_profile_wire import record
from app.v3.relocation_pair_inputs import PAIR_POLICY_VERSION, PreparedRelocationPair
from app.v3.relocation_pair_rules import input_family

REPORT_VERSION = "qoima-relocation-pair-report-0.1.0"


def build_pair_report(
    pair: PreparedRelocationPair,
    baseline_run: dict[str, Any],
    candidate_run: dict[str, Any],
    baseline_outcome: CoordinatorOutcome,
    candidate_outcome: CoordinatorOutcome,
) -> dict[str, Any]:
    left, right = _side(baseline_run, baseline_outcome), _side(candidate_run, candidate_outcome)
    identity = {
        "schema_version": REPORT_VERSION,
        "policy_version": PAIR_POLICY_VERSION,
        "scenario": pair.scenario,
        "pair_input_hash": pair.input_hash,
        "common_input_hash": pair.common_input_hash,
    }
    return {
        **identity,
        "comparison_id": _hash(identity),
        "input_family": input_family(pair.baseline),
        "status": "partial" if "partial" in (left["status"], right["status"]) else "complete",
        "contract_status": "proposal",
        "executions": 2,
        "no_op": not pair.candidate.choices.jobs,
        "full_n1_acceptance": False,
        "full_v3_acceptance": False,
        "common_identity": _common_identity(pair, baseline_run),
        "baseline": left,
        "candidate": right,
        "windows": {
            key: _window(baseline_run, candidate_run, key) for key in ("at_horizon", "at_end")
        },
        "window_rules": _window_rules(),
        "events_equal": left["event_sha256"] == right["event_sha256"],
        "observations_equal": left["observation_sha256"] == right["observation_sha256"],
    }


def _hash(value: Any) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _side(run: dict[str, Any], outcome: CoordinatorOutcome) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "status": outcome.status,
        "outcome_kind": run["outcome_kind"],
        "event_sha256": event_hash(outcome),
        "observation_sha256": observation_hash(outcome),
        "raw_boundaries": {
            "business_complete_tick": outcome.business_complete_tick,
            "resource_drained_tick": outcome.resource_drained_tick,
            "observation_end_tick": outcome.observation_end_tick,
        },
        "metrics": run["metrics"],
    }


def _common_identity(pair: PreparedRelocationPair, run: dict[str, Any]) -> dict[str, Any]:
    common = pair.baseline.profile.coordinator
    flow = common.world.receipts.flow
    resources = common.unit_resources
    carts = tuple(c.cart.cart_id for c in resources.carts) if resources else (flow.cart.cart_id,)
    return {
        "source_revision": flow.source_revision,
        "source_hashes": record(flow.source_hashes),
        "initial_stock_sha256": _hash(record(flow.stock)),
        "physical_profile_sha256": _hash(record(common)),
        "registry_common_hash": run["registry_common_hash"],
        "actor_ids": sorted(a.actor_id for a in flow.actors),
        "cart_ids": sorted(carts),
        "horizon_tick": run["horizon_tick"],
        "end_tick_limit": run["end_tick_limit"],
    }


def _window(left_run: dict[str, Any], right_run: dict[str, Any], key: str) -> dict[str, Any]:
    left, right = left_run["metrics"]["common"][key], right_run["metrics"]["common"][key]
    baseline_paid, candidate_paid = (
        integer(left["labor"]["paid_ticks"]),
        integer(right["labor"]["paid_ticks"]),
    )
    return {
        "baseline_tick": integer(left["tick"]),
        "candidate_tick": integer(right["tick"]),
        "baseline_paid_ticks": baseline_paid,
        "candidate_paid_ticks": candidate_paid,
        "net_paid_ticks": baseline_paid - candidate_paid,
        "baseline_relocation_paid_ticks": integer(left_run["metrics"][key]["paid_ticks"]),
        "candidate_relocation_paid_ticks": integer(right_run["metrics"][key]["paid_ticks"]),
        "customer_work": {kind: _business(left[kind], right[kind]) for kind in ("unit", "whole")},
    }


def _business(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        "baseline": left,
        "candidate": right,
        **{
            key + "_delta": integer(right[key]) - integer(left[key])
            for key in ("completed_orders", "completed_units", "backlog_orders")
        },
    }


def _window_rules() -> dict[str, str]:
    return {
        "at_horizon": "common H; settled counts <=H; paid integral [0,H)",
        "at_end": "each actual observation end; common cap; ticks may differ",
        "net_paid_ticks": "baseline common paid minus candidate common paid",
        "relocation_paid_ticks": (
            "diagnostic subset already included in common paid; no second deduction"
        ),
        "customer_work": (
            "actual unit/whole business handovers and completed-cycle samples; "
            "count deltas candidate minus baseline"
        ),
        "raw_business_complete_tick": (
            "includes relocation placement; not a customer throughput measure"
        ),
    }
