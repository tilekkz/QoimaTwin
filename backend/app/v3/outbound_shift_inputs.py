"""Strict public N1 input compilation and fresh source reauthentication, never execution."""

from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.outbound_shift_materialize import _materialize
from app.v3.outbound_shift_models import INPUT_SCOPE, INPUT_VERSION, OutboundShiftInputs
from app.v3.outbound_shift_source import load_outbound_shift_scenario, source_roots
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_policy import fields, parse_workload_policy, validate_policy


def compile_outbound_shift(
    base_root: Path,
    adaptation_root: Path,
    policy: WorkloadPolicy,
) -> OutboundShiftInputs:
    """Caller supplies an explicit clock/count policy, never replacement source weights."""
    validate_policy(policy)
    scenario = load_outbound_shift_scenario(base_root, adaptation_root)
    return _materialize(scenario, policy)


def load_outbound_shift_inputs(raw: bytes) -> OutboundShiftInputs:
    if type(raw) is not bytes:
        raise ValueError("Outbound shift inputs require exact immutable bytes")
    value = fields(
        parse_json(raw),
        {
            "schema_version",
            "scope",
            "scenario",
            "choices",
            "workload",
            "operational_admission",
            "full_n1_acceptance",
        },
    )
    if canonical_bytes(value) != raw:
        raise ValueError("Outbound shift inputs require canonical object bytes")
    if value["schema_version"] != INPUT_VERSION or value["scope"] != INPUT_SCOPE:
        raise ValueError("Unsupported outbound shift input identity")
    policy = parse_workload_policy(value["choices"])
    expected = compile_outbound_shift(*source_roots(), policy)
    if expected.frozen_bytes != raw:
        raise ValueError("Outbound shift differs from exact source, projection or offered stream")
    return expected


def verify_outbound_shift_inputs(inputs: OutboundShiftInputs) -> OutboundShiftInputs:
    """Return fresh authoritative values; exact nested types reject bool/int aliases."""
    if type(inputs) is not OutboundShiftInputs:
        raise ValueError("Exact source-bound OutboundShiftInputs required")
    expected = load_outbound_shift_inputs(inputs.frozen_bytes)
    require_same_authority(inputs, expected)
    return expected
