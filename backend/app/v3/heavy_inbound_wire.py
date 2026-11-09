"""Closed canonical declaration and recomputed complete offered stream."""

from dataclasses import fields
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.flow_profile_wire import record
from app.v3.heavy_inbound_models import SCOPE, VERSION, HeavyInboundInputs, HeavyInboundReceipt
from app.v3.workload_policy import fields as object_fields
from app.v3.workload_wire import policy_dict


def receipts_from_wire(value: object) -> tuple[HeavyInboundReceipt, ...]:
    if type(value) is not list:
        raise ValueError("HEAVY_RECEIPTS_ARRAY_REQUIRED")
    names = {field.name for field in fields(HeavyInboundReceipt)}
    return tuple(HeavyInboundReceipt(**object_fields(row, names)) for row in value)


def inputs_record(value: HeavyInboundInputs) -> dict[str, Any]:
    authority = value.authority
    return {
        "schema_version": VERSION,
        "scope": SCOPE,
        "policy": policy_dict(authority.baseline.policy),
        "additions": record(value.additions),
        "authority": {
            "source_revision": authority.source_revision,
            "layout_content_hash": authority.layout_content_hash,
            "raw_fingerprints": record(authority.raw_fingerprints),
            "baseline_input_raw": authority.baseline_input_raw.decode("utf-8"),
            "baseline_assignment_raw": authority.baseline_assignment_raw.decode("utf-8"),
            "initial_hus": record(authority.initial_hus),
            "baseline": parse_json(authority.baseline_bytes),
        },
        "receipts": record(value.receipts),
        "deltas": record(value.deltas),
        "postshift_jobs": parse_json(value.offered_bytes),
        "accepted_receipt_count": value.accepted_receipt_count,
        "operational_admission": value.operational_admission,
        "full_n2_acceptance": value.full_n2_acceptance,
    }
