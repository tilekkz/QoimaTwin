"""Source-bound numerical forecast facts, distinct from legacy visits and any admission."""

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from app.v3.offer_history_models import OfferHistoryInputs
from app.v3.workload_models import WorkloadSource

FORECAST_VERSION = "qoima-v3-offered-hu-forecast-0.1.0"
TEMPORAL_POLICY = "42train_14rolling_validation_28warmup_fresh56day_final_v1"
FLOAT_POLICY = "binary64_prediction_error_exact_observed_count_v2"
type Predictions = tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True, slots=True)
class OfferForecastEvaluation:
    absolute_error: Fraction
    actual_offers: Fraction
    wape: Fraction | None
    validation_rows: int
    validation_fit_rows: int
    final_fit_rows: int
    first_day: str
    last_day: str


@dataclass(frozen=True, slots=True)
class OfferForecastCPU:
    total_s: float
    validation_s: float
    final_fit_s: float


@dataclass(frozen=True, slots=True)
class OfferForecast:
    source: WorkloadSource
    history: OfferHistoryInputs
    model: str
    predictions: Predictions
    training_baseline: Predictions
    evaluation: OfferForecastEvaluation
    kernel_identity: tuple[tuple[str, str], ...]
    frozen_bytes: bytes
    input_hash: str
    measurements: OfferForecastCPU = field(compare=False, repr=False)

    @property
    def operational_admission(self) -> Literal[False]:
        return False
