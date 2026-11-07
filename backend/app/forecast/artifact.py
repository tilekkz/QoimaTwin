"""Hashable snapshots keep runtime measurements outside semantic identity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Literal

from app.forecast.history import _number
from app.storage.canonical_json import sha256_hex

type Model = Literal["mean28", "hgb"]
PROTOCOL = "qoima-forecast-temporal-1"
FEATURES = ("lag1", "lag7", "lag14", "lag28", "mean7", "mean28", "weekday", "onehotSKU")
HGB_PARAMETERS = (
    ("loss", "poisson"),
    ("max_iter", 150),
    ("max_leaf_nodes", 15),
    ("learning_rate", 0.06),
    ("l2_regularization", 1.0),
    ("random_state", 42),
    ("early_stopping", False),
)


@dataclass(frozen=True, slots=True)
class Predictions:
    values: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        values = tuple((sku, _number(value)) for sku, value in self.values)
        if not values or any(not isinstance(sku, str) or not sku for sku, _ in values):
            raise ValueError("predictions require nonempty SKU IDs")
        if tuple(sorted({sku for sku, _ in values})) != tuple(sku for sku, _ in values):
            raise ValueError("predictions require sorted unique SKU IDs")
        object.__setattr__(self, "values", values)

    @property
    def visits_by_sku(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.values))


@dataclass(frozen=True, slots=True)
class ValidationEvaluation:
    absolute_error: float
    actual_visits: float
    target_rows: int
    first_day: date
    last_day: date
    fit_target_rows: int

    @property
    def wape(self) -> float | None:
        return self.absolute_error / self.actual_visits if self.actual_visits else None

    def to_dict(self) -> dict[str, object]:
        return {
            "wape": self.wape,
            "absolute_error": self.absolute_error,
            "actual_visits": self.actual_visits,
            "target_rows": self.target_rows,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "fit_target_rows": self.fit_target_rows,
        }


@dataclass(frozen=True, slots=True)
class ForecastSnapshot:
    model: Model
    history_hash: str
    cutoff: date
    test_day: date
    predictions: Predictions
    training_baseline: Predictions
    validation: ValidationEvaluation
    synthetic_training: bool
    cpu_time_s: float
    validation_cpu_time_s: float
    final_fit_cpu_time_s: float

    @property
    def training_visits_by_sku(self) -> Mapping[str, float]:
        return self.training_baseline.visits_by_sku

    def semantic_dict(self) -> dict[str, object]:
        return {
            "protocol": PROTOCOL,
            "model": self.model,
            "history_hash": self.history_hash,
            "cutoff": self.cutoff.isoformat(),
            "test_day": self.test_day.isoformat(),
            "predictions": {"visits_by_sku": dict(self.predictions.values)},
            "training_visits_by_sku": dict(self.training_baseline.values),
            "validation": self.validation.to_dict(),
            "synthetic_training": self.synthetic_training,
            "parameters": dict(HGB_PARAMETERS) if self.model == "hgb" else {"window": 28},
            "features": FEATURES if self.model == "hgb" else ("mean28",),
            "full_day_s": 28800,
            "train_days": 42,
            "validation_days": 14,
            "warmup_days": 28,
            "final_fit_target_rows": 28 * len(self.predictions.values),
        }

    @property
    def semantic_id(self) -> str:
        return sha256_hex(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            **self.semantic_dict(),
            "semantic_id": self.semantic_id,
            "cpu_time_s": self.cpu_time_s,
            "validation_cpu_time_s": self.validation_cpu_time_s,
            "final_fit_cpu_time_s": self.final_fit_cpu_time_s,
        }
