"""Forecast composition offers are planning inputs, never actual offered work or stock."""

from dataclasses import dataclass
from typing import Literal

from app.v3.input_models import HandlingUnit
from app.v3.workload_models import DemandWeight, Quota, WorkloadJob, WorkloadPolicy, WorkloadSource

VERSION = "qoima-offer-forecast-projection-0.1.0"
SCOPE = "predicted_outbound_whole_hu_composition_fixed_budget"


@dataclass(frozen=True, slots=True)
class OfferProjectionChoices:
    policy: WorkloadPolicy
    port_mix_mode: Literal["source_c10", "explicit"]
    port_mix: tuple[DemandWeight, ...]


@dataclass(frozen=True, slots=True)
class ProjectionOffers:
    port_mix: tuple[DemandWeight, ...]
    weights: tuple[DemandWeight, ...]
    quotas: tuple[Quota, ...]
    jobs: tuple[WorkloadJob, ...]
    population_id: str


@dataclass(frozen=True, slots=True)
class OfferProjectionInputs:
    forecast_bytes: bytes
    forecast_id: str
    source: WorkloadSource
    initial_hus: tuple[HandlingUnit, ...]
    choices: OfferProjectionChoices
    offers: ProjectionOffers
    frozen_bytes: bytes
    input_hash: str
    operational_admission: Literal[False] = False
    actual_test_stream: Literal[False] = False
    throughput_claim: Literal[False] = False
