"""One frozen temporal validation followed by a final historical fit."""

from __future__ import annotations

import math
from time import process_time

from app.forecast.artifact import ForecastSnapshot, Model, Predictions, ValidationEvaluation
from app.forecast.history import ForecastHistory, target_day


def mean28(history: ForecastHistory, offset: int) -> tuple[float, ...]:
    if not 28 <= offset <= 56:
        raise ValueError("target needs 28 observed prior days and cannot exceed test_day")
    return tuple(
        math.fsum(row[j] for row in history.visits[offset - 28 : offset]) / 28
        for j in range(len(history.sku_ids))
    )


def _evaluate(
    history: ForecastHistory,
    validation: tuple[tuple[float, ...], ...],
) -> ValidationEvaluation:
    absolute = math.fsum(
        abs(pred - actual)
        for predicted, observed in zip(validation, history.visits[42:], strict=True)
        for pred, actual in zip(predicted, observed, strict=True)
    )
    return ValidationEvaluation(
        absolute,
        math.fsum(v for row in history.visits[42:] for v in row),
        14 * len(history.sku_ids),
        target_day(history, 42),
        target_day(history, 55),
        14 * len(history.sku_ids),
    )


def fit_forecast(history: ForecastHistory, model: Model = "mean28") -> ForecastSnapshot:
    if model not in ("mean28", "hgb"):
        raise ValueError("unknown forecast model")
    started = process_time()
    if model == "hgb":
        from app.forecast.hgb import predict_hgb

        validation, final, validation_cpu, final_cpu = predict_hgb(history)
    else:
        validation = tuple(mean28(history, i) for i in range(42, 56))
        validation_cpu = process_time() - started
        final_started = process_time()
        final = mean28(history, 56)
        final_cpu = process_time() - final_started
    baseline = tuple(
        math.fsum(row[j] for row in history.visits[:42]) / 42 for j in range(len(history.sku_ids))
    )
    evaluation = _evaluate(history, validation)
    return ForecastSnapshot(
        model,
        history.history_hash,
        target_day(history, 55),
        history.test_day,
        Predictions(tuple(zip(history.sku_ids, final, strict=True))),
        Predictions(tuple(zip(history.sku_ids, baseline, strict=True))),
        evaluation,
        history.synthetic_training,
        process_time() - started,
        validation_cpu,
        final_cpu,
    )
