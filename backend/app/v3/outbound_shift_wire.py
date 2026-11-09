"""Explicit source, projection and byte-preserving provenance identities."""

from dataclasses import asdict
from typing import Any

from app.v3.outbound_shift_models import N1Scenario
from app.v3.workload_wire import source_dict


def scenario_record(scenario: N1Scenario) -> dict[str, Any]:
    """Hash preimage excludes only its own digest; raw source whitespace is retained."""
    return {
        "schema_version": scenario.version,
        "scenario_id": scenario.scenario_id,
        "projection_policy": scenario.projection_policy,
        "projected_fields": list(scenario.projected_fields),
        "baseline": source_dict(scenario.baseline),
        "postshift": source_dict(scenario.postshift),
        "initial_placements": [asdict(place) for place in scenario.initial_placements],
        "raw_sources": [
            {
                "key": doc.key,
                "path": doc.path,
                "raw": doc.raw.decode("utf-8"),
                "raw_sha256": doc.raw_sha256,
            }
            for doc in scenario.raw_sources
        ],
        "legacy_source_revision": scenario.legacy_source_revision,
        "legacy_scenario_id": scenario.legacy_scenario_id,
        "period_unit": scenario.period_unit,
        "excluded_inbound_skus": list(scenario.excluded_inbound_skus),
    }


def scenario_dict(scenario: N1Scenario) -> dict[str, Any]:
    return {**scenario_record(scenario), "scenario_hash": scenario.scenario_hash}
