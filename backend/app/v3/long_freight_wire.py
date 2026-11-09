"""Closed canonical prerequisite envelope; derived records are never trusted on load."""

from dataclasses import fields
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.flow_profile_wire import record
from app.v3.long_freight_models import SCOPE, VERSION, LongFreightRequest, LongFreightRequirements
from app.v3.workload_policy import fields as object_fields
from app.v3.workload_wire import policy_dict


def request_from_wire(value: object) -> LongFreightRequest:
    row = object_fields(value, {field.name for field in fields(LongFreightRequest)})
    return LongFreightRequest(**row)


def requirements_record(value: LongFreightRequirements) -> dict[str, Any]:
    authority = value.authority
    return {
        "schema_version": VERSION,
        "scope": SCOPE,
        "request": record(value.request),
        "policy": policy_dict(authority.workload.policy),
        "authority": {
            "source_revision": authority.source_revision,
            "layout_content_hash": authority.layout_content_hash,
            "raw_fingerprints": record(authority.raw_fingerprints),
            "baseline_input_raw": authority.baseline_input_raw.decode("utf-8"),
            "baseline_assignment_raw": authority.baseline_assignment_raw.decode("utf-8"),
            "initial_hus": record(authority.initial_hus),
            "workload": parse_json(authority.workload_bytes),
        },
        "static": record(value.static),
        "blockers": record(value.blockers),
        "operational_admission": value.operational_admission,
        "full_n3_acceptance": value.full_n3_acceptance,
    }
