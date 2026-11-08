"""Side-by-side native metrics with explicit limits; no proxy acceptance substitution."""

from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile
from app.v3.coordinator_pair_evidence import helper_evidence
from app.v3.coordinator_pair_models import PAIR_VERSION, PairScenario
from app.v3.flow_profile_wire import record


def event_hash(outcome: CoordinatorOutcome) -> str:
    return sha256(canonical_bytes(record(outcome.events))).hexdigest()


def observation_hash(outcome: CoordinatorOutcome) -> str:
    return sha256(
        canonical_bytes(
            record(
                (
                    outcome.status,
                    outcome.at_horizon,
                    outcome.at_end,
                    outcome.checkpoints,
                    outcome.business_complete_tick,
                    outcome.resource_drained_tick,
                    outcome.observation_end_tick,
                    outcome.staffing_status,
                    outcome.constraint_violations,
                )
            )
        )
    ).hexdigest()


def side(run: dict[str, Any], outcome: CoordinatorOutcome) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "event_sha256": event_hash(outcome),
        "observation_sha256": observation_hash(outcome),
        "status": outcome.status,
        "staffing_status": outcome.staffing_status,
        "business_complete_tick": outcome.business_complete_tick,
        "resource_drained_tick": outcome.resource_drained_tick,
        "observation_end_tick": outcome.observation_end_tick,
        "metrics": run["metrics"],
    }


def scenario_evidence(
    scenario: PairScenario,
    profile: CoordinatorProfile,
    baseline: CoordinatorOutcome,
    candidate: CoordinatorOutcome,
) -> tuple[bool, dict[str, Any]]:
    if scenario == "N0":
        events_equal = event_hash(baseline) == event_hash(candidate)
        observations_equal = observation_hash(baseline) == observation_hash(candidate)
        return events_equal and observations_equal, {
            "events_equal": events_equal,
            "observations_equal": observations_equal,
        }
    helpers = helper_evidence(profile, candidate)
    return all(row["demonstrated"] for row in helpers) and len(helpers) == 2, {
        "helpers": helpers,
        "station_admission_evidence": "strict_native_resource_and_custody_validation",
    }


def report(
    scenario: PairScenario,
    common_hash: str,
    scope: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    demonstrated: bool,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "version": PAIR_VERSION,
        "scenario": scenario,
        "scope": scope,
        "common_input_hash": common_hash,
        "baseline_input_hash": baseline["input_hash"],
        "candidate_input_hash": candidate["input_hash"],
    }
    return {
        **identity,
        "comparison_id": sha256(canonical_bytes(identity)).hexdigest(),
        "contract_status": "proposal",
        "executions": 2,
        "verdict": "demonstrated" if demonstrated else "not_demonstrated",
        "full_v3_acceptance": False,
        "frontend_adapter_supported": False,
        "capabilities": {"N0": True, "N1": False, "N2": False, "N3": False, "N4": True},
        "baseline": baseline,
        "candidate": candidate,
        "evidence": evidence,
        "comparison_windows": {
            "at_horizon": "common H; counts <= H; exposure [0,H)",
            "at_end": "each actual observation end; common cap, possibly different denominators",
        },
        "limitations": [
            "Only the declared bounded coordinator flow is executed.",
            "Synthetic clocks and material recipes remain input assumptions.",
            "No N1/N2/N3 execution, paid relocation proxy, or human mesh proof is claimed.",
            "Role assignment exposure is not worker busy utilization.",
        ],
    }
