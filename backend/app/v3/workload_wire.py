"""Canonical proposal projection with exact rational values and explicit stock scope."""

from dataclasses import asdict
from fractions import Fraction
from typing import Any

from app.v3.workload_models import (
    Quota,
    TimedWorkload,
    WholeHUTemplate,
    WorkloadPolicy,
    WorkloadSource,
)
from app.v3.workload_policy import POLICY_SCHEMA, POLICY_VERSION

MATERIALIZER_VERSION = "qoima-v3-workload-0.1.0"
STOCK_BINDING = "offered_inbound_and_unallocated_outbound_whole_hus"


def rational(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def template_dict(template: WholeHUTemplate) -> dict[str, Any]:
    return {
        "sku_id": template.sku_id,
        "archetype_id": template.archetype_id,
        "quantity_units": template.quantity_units,
        "dimensions_xyz_m": [rational(v) for v in template.dimensions_xyz_m],
        "gross_mass_kg": rational(template.gross_mass_kg),
        "orientation_id": template.orientation_id,
        "source_lot_id": template.source_lot_id,
        "initial_hu_ids": sorted(template.initial_hu_ids),
        "cargo_record_sha256": template.cargo_record_sha256,
        "packing_recipe_sha256": template.packing_recipe_sha256,
    }


def source_dict(source: WorkloadSource) -> dict[str, Any]:
    return {
        "source_revision": source.source_revision,
        "layout_content_hash": source.layout_content_hash,
        "raw_fingerprints": [list(row) for row in sorted(source.raw_fingerprints)],
        "document_fingerprints": [list(row) for row in sorted(source.document_fingerprints)],
        "templates": [template_dict(t) for t in sorted(source.templates, key=lambda t: t.sku_id)],
        "weights": {
            direction: [
                {"sku_id": row.sku_id, "port_id": row.port_id, "weight": rational(row.weight)}
                for row in sorted(weights, key=lambda row: (row.sku_id, row.port_id))
            ]
            for direction, weights in (
                ("inbound", source.inbound_weights),
                ("outbound", source.outbound_weights),
            )
        },
    }


def policy_dict(policy: WorkloadPolicy) -> dict[str, Any]:
    return {
        "schema_id": POLICY_SCHEMA,
        "schema_version": POLICY_VERSION,
        "horizon_tick": policy.horizon_tick,
        "offered_hus": {"inbound": policy.inbound_hus, "outbound": policy.outbound_hus},
        "calendar": {
            "kind": policy.calendar,
            "windows": [
                {"start_tick": w.start_tick, "end_tick": w.end_tick, "weight": rational(w.weight)}
                for w in policy.windows
            ],
        },
    }


def quota_dict(quota: Quota) -> dict[str, Any]:
    return {
        "sku_id": quota.sku_id,
        "port_id": quota.port_id,
        "count": quota.count,
        "expected": rational(quota.expected),
        "delta": rational(quota.delta),
    }


def workload_dict(workload: TimedWorkload, *, include_id: bool = True) -> dict[str, Any]:
    result = {
        "schema_id": "qoima.timed-workload.v3-proposal",
        "schema_version": "0.1.0",
        "materializer_version": MATERIALIZER_VERSION,
        "data_kind": "synthetic_timed_workload",
        "operational_admission": False,
        "stock_binding": STOCK_BINDING,
        "clock": {"ticks_per_second": 1_000_000},
        "source": source_dict(workload.source),
        "policy": policy_dict(workload.policy),
        "population_id": workload.population_id,
        "quotas": {
            "inbound": [quota_dict(q) for q in workload.inbound_quotas],
            "outbound": [quota_dict(q) for q in workload.outbound_quotas],
        },
        "jobs": [asdict(job) for job in workload.jobs],
    }
    if include_id:
        result["workload_id"] = workload.workload_id
    return result
