"""Canonical N1 pair inputs retain both complete independently verified arms."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Literal

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.relocation_models import BoundRelocation
from app.v3.relocation_pair_rules import (
    input_family,
    require_n1_pair,
    require_same_family,
    scenario_name,
)
from app.v3.relocation_run_inputs import load_run_inputs, verify_inputs
from app.v3.staff_registry_values import object_fields
from app.v3.stock_validation import require

PAIR_VERSION = "qoima-relocation-pair-inputs-0.1.0"
PAIR_POLICY_VERSION = "n1-single-intact-manual-relocation-jobs-only-v1"
PAIR_SCOPE = "manual_relocation_jobs_only_comparison_inputs"


@dataclass(frozen=True, slots=True)
class PreparedRelocationPair:
    scenario: Literal["N1"]
    baseline: BoundRelocation
    candidate: BoundRelocation
    common_input_hash: str
    frozen_bytes: bytes
    input_hash: str


def prepare_relocation_pair(
    baseline: BoundRelocation, candidate: BoundRelocation, *, scenario: object
) -> PreparedRelocationPair:
    name = scenario_name(scenario)
    require_same_family(baseline, candidate)
    verify_inputs(baseline)
    verify_inputs(candidate)
    return _prepare(baseline, candidate, name)


def _prepare(
    baseline: BoundRelocation, candidate: BoundRelocation, scenario: Literal["N1"]
) -> PreparedRelocationPair:
    require_n1_pair(baseline, candidate)
    common_hash = sha256(baseline.common_inputs).hexdigest()
    raw = canonical_bytes(
        {
            "schema_version": PAIR_VERSION,
            "policy_version": PAIR_POLICY_VERSION,
            "scope": PAIR_SCOPE,
            "scenario": scenario,
            "input_family": input_family(baseline),
            "common_input_hash": common_hash,
            "baseline_input_hash": baseline.input_hash,
            "candidate_input_hash": candidate.input_hash,
            "baseline_inputs": parse_json(baseline.frozen_bytes),
            "candidate_inputs": parse_json(candidate.frozen_bytes),
        }
    )
    return PreparedRelocationPair(
        scenario, baseline, candidate, common_hash, raw, sha256(raw).hexdigest()
    )


def load_relocation_pair_inputs(raw: bytes) -> PreparedRelocationPair:
    require(type(raw) is bytes, "Exact immutable relocation pair bytes required")
    value = _envelope(raw)
    name = scenario_name(value["scenario"])
    baseline = load_run_inputs(canonical_bytes(value["baseline_inputs"]))
    candidate = load_run_inputs(canonical_bytes(value["candidate_inputs"]))
    expected = _prepare(baseline, candidate, name)
    require(expected.frozen_bytes == raw, "Relocation pair identity or policy metadata differs")
    return expected


def _envelope(raw: bytes) -> dict[str, Any]:
    value = object_fields(
        parse_json(raw),
        "schema_version policy_version scope scenario input_family common_input_hash "
        "baseline_input_hash candidate_input_hash baseline_inputs candidate_inputs",
    )
    require(canonical_bytes(value) == raw, "Canonical relocation pair object bytes required")
    require(value["schema_version"] == PAIR_VERSION, "Relocation pair input version")
    require(value["policy_version"] == PAIR_POLICY_VERSION, "Relocation pair policy version")
    require(value["scope"] == PAIR_SCOPE, "Relocation pair scope")
    for key in ("baseline", "candidate"):
        digest = sha256(canonical_bytes(value[f"{key}_inputs"])).hexdigest()
        require(value[f"{key}_input_hash"] == digest, "Relocation pair arm input hash differs")
    return value


def verify_relocation_pair(pair: PreparedRelocationPair) -> PreparedRelocationPair:
    require(type(pair) is PreparedRelocationPair, "Exact prepared relocation pair required")
    expected = load_relocation_pair_inputs(pair.frozen_bytes)
    require_same_authority(pair, expected)
    return expected
