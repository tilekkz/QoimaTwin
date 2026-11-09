"""Authenticate N2 extra offers against fresh C10; no stock credit or runtime authority."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.flow_profile_wire import record
from app.v3.heavy_inbound_augment import augment_offers
from app.v3.heavy_inbound_models import SCOPE, VERSION, HeavyInboundInputs, HeavyInboundReceipt
from app.v3.heavy_inbound_source import load_baseline
from app.v3.heavy_inbound_wire import inputs_record, receipts_from_wire
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_policy import fields, parse_workload_policy


def compile_heavy_inbound_inputs(
    policy: WorkloadPolicy,
    additions: tuple[HeavyInboundReceipt, ...],
) -> HeavyInboundInputs:
    authority, ports = load_baseline(policy)
    augmentation = augment_offers(authority.baseline, additions, ports)
    result = HeavyInboundInputs(
        authority,
        tuple(r.declaration for r in augmentation.receipts),
        augmentation.receipts,
        augmentation.deltas,
        augmentation.postshift_jobs,
        canonical_bytes(record(augmentation.postshift_jobs)),
        b"",
        "",
    )
    raw = canonical_bytes(inputs_record(result))
    return replace(result, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def load_heavy_inbound_inputs(raw: bytes) -> HeavyInboundInputs:
    if type(raw) is not bytes:
        raise ValueError("EXACT_HEAVY_INBOUND_BYTES_REQUIRED")
    value = fields(
        parse_json(raw),
        {
            "schema_version",
            "scope",
            "policy",
            "additions",
            "authority",
            "receipts",
            "deltas",
            "postshift_jobs",
            "accepted_receipt_count",
            "operational_admission",
            "full_n2_acceptance",
        },
    )
    if canonical_bytes(value) != raw:
        raise ValueError("CANONICAL_HEAVY_INBOUND_BYTES_REQUIRED")
    if value["schema_version"] != VERSION or value["scope"] != SCOPE:
        raise ValueError("UNSUPPORTED_HEAVY_INBOUND_VERSION")
    result = compile_heavy_inbound_inputs(
        parse_workload_policy(value["policy"]), receipts_from_wire(value["additions"])
    )
    if result.frozen_bytes != raw:
        raise ValueError("HEAVY_SOURCE_OR_OFFERED_STREAM_CHANGED")
    return result


def verify_heavy_inbound_inputs(value: HeavyInboundInputs) -> HeavyInboundInputs:
    if type(value) is not HeavyInboundInputs:
        raise ValueError("EXACT_HEAVY_INBOUND_INPUTS_REQUIRED")
    expected = load_heavy_inbound_inputs(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
