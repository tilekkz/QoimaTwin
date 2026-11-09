"""Forecast planning decisions are distinct from C11 and actual future workload authority."""

from dataclasses import dataclass
from typing import Literal

from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.outbound_placement_models import (
    PlacementCandidate,
    PlacementChoices,
    PlacementEvaluation,
)
from app.v3.outbound_shift_models import BaselinePlacement

VERSION = "qoima-forecast-placement-decision-0.1.0"
SCOPE = "predicted_offers_single_original_hu_planning_only"


@dataclass(frozen=True, slots=True)
class ForecastPlacementDecision:
    stock: ForecastBoundStock
    forecast_id: str
    projection_id: str
    stock_input_hash: str
    choices: PlacementChoices
    evaluations: tuple[PlacementEvaluation, ...]
    selected: PlacementCandidate | None
    no_op: bool
    selection_reason: str
    placements: tuple[BaselinePlacement, ...]
    choices_bytes: bytes
    frozen_bytes: bytes
    input_hash: str
    operational_admission: Literal[False] = False
    actual_test_stream: Literal[False] = False
    full_n1_acceptance: Literal[False] = False
