"""Immutable N1 source projections and offered input bytes; no operational admission."""

from dataclasses import dataclass
from typing import Literal

from app.v3.workload_models import TimedWorkload, WorkloadPolicy, WorkloadSource

SCENARIO_VERSION = "qoima-n1-outbound-shift-scenario-0.1.0"
INPUT_VERSION = "qoima-n1-outbound-shift-inputs-0.1.0"
PROJECTION_POLICY = "c10_intensities_c11_outbound_mix_only"
INPUT_SCOPE = "source_bound_outbound_only_offers"


@dataclass(frozen=True, slots=True)
class ShiftSourceDocument:
    key: str
    path: str
    raw: bytes
    raw_sha256: str


@dataclass(frozen=True, slots=True)
class BaselinePlacement:
    hu_id: str
    sku_id: str
    slot_id: str
    module_id: str


@dataclass(frozen=True, slots=True)
class N1Scenario:
    version: str
    scenario_id: Literal["N1"]
    projection_policy: str
    projected_fields: tuple[str, ...]
    baseline: WorkloadSource
    postshift: WorkloadSource
    initial_placements: tuple[BaselinePlacement, ...]
    raw_sources: tuple[ShiftSourceDocument, ...]
    legacy_source_revision: str
    legacy_scenario_id: str
    period_unit: str
    excluded_inbound_skus: tuple[str, ...]
    scenario_hash: str


@dataclass(frozen=True, slots=True)
class OutboundShiftInputs:
    scenario: N1Scenario
    policy: WorkloadPolicy
    workload: TimedWorkload
    scenario_bytes: bytes
    policy_bytes: bytes
    workload_bytes: bytes
    frozen_bytes: bytes
    input_hash: str
