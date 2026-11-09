"""N3 source-backed prerequisite compilation and fresh closed-envelope verification."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.long_freight_checks import static_checks
from app.v3.long_freight_models import SCOPE, VERSION, LongFreightRequest, LongFreightRequirements
from app.v3.long_freight_obligations import obligations
from app.v3.long_freight_source import load_source
from app.v3.long_freight_wire import request_from_wire, requirements_record
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_policy import fields, parse_workload_policy


def compile_long_freight_requirements(
    request: LongFreightRequest,
    policy: WorkloadPolicy,
) -> LongFreightRequirements:
    source = load_source(request, policy)
    result = LongFreightRequirements(
        request,
        source.authority,
        static_checks(source, request),
        obligations(),
        b"",
        "",
    )
    raw = canonical_bytes(requirements_record(result))
    return replace(result, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def load_long_freight_requirements(raw: bytes) -> LongFreightRequirements:
    if type(raw) is not bytes:
        raise ValueError("EXACT_LONG_FREIGHT_BYTES_REQUIRED")
    value = fields(
        parse_json(raw),
        {
            "schema_version",
            "scope",
            "request",
            "policy",
            "authority",
            "static",
            "blockers",
            "operational_admission",
            "full_n3_acceptance",
        },
    )
    if canonical_bytes(value) != raw:
        raise ValueError("CANONICAL_LONG_FREIGHT_BYTES_REQUIRED")
    if value["schema_version"] != VERSION or value["scope"] != SCOPE:
        raise ValueError("UNSUPPORTED_LONG_FREIGHT_VERSION")
    result = compile_long_freight_requirements(
        request_from_wire(value["request"]),
        parse_workload_policy(value["policy"]),
    )
    if result.frozen_bytes != raw:
        raise ValueError("LONG_FREIGHT_SOURCE_OR_DERIVED_AUTHORITY_CHANGED")
    return result


def verify_long_freight_requirements(value: LongFreightRequirements) -> LongFreightRequirements:
    if type(value) is not LongFreightRequirements:
        raise ValueError("EXACT_LONG_FREIGHT_REQUIREMENTS_REQUIRED")
    expected = load_long_freight_requirements(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
