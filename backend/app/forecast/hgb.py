"""Fixed Poisson HGB; features at t depend exclusively on observations before t."""

from __future__ import annotations

import math
from collections.abc import Sequence
from time import process_time

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore[import-untyped]
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from app.forecast.history import ForecastHistory, target_day


def feature_rows(
    history: ForecastHistory,
    offsets: Sequence[int],
) -> tuple[tuple[float, ...], ...]:
    result = []
    for offset in offsets:
        if not 28 <= offset <= 56:
            raise ValueError("features require 28 prior observed days; no dates beyond test_day")
        for j in range(len(history.sku_ids)):
            lags = tuple(history.visits[offset - lag][j] for lag in (1, 7, 14, 28))
            means = tuple(
                math.fsum(row[j] for row in history.visits[offset - w : offset]) / w
                for w in (7, 28)
            )
            weekday = (float(target_day(history, offset).weekday()),)
            onehot = tuple(float(j == k) for k in range(len(history.sku_ids)))
            result.append(lags + means + weekday + onehot)
    return tuple(result)


def _fit_predict(
    history: ForecastHistory,
    stop: int,
    targets: Sequence[int],
) -> tuple[tuple[float, ...], ...]:
    x = np.asarray(feature_rows(history, tuple(range(28, stop))), dtype=np.float64)
    y = np.asarray([v for row in history.visits[28:stop] for v in row], dtype=np.float64)
    if not y.any():
        # Poisson's all-zero optimum is the zero boundary; sklearn requires sum(y)>0.
        return tuple(tuple(0.0 for _ in history.sku_ids) for _ in targets)
    estimator = HistGradientBoostingRegressor(
        loss="poisson",
        max_iter=150,
        max_leaf_nodes=15,
        learning_rate=0.06,
        l2_regularization=1.0,
        random_state=42,
        early_stopping=False,
    )
    with threadpool_limits(limits=1):
        estimator.fit(x, y)
        predictions = estimator.predict(
            np.asarray(feature_rows(history, targets), dtype=np.float64)
        )
    flat = tuple(float(value) for value in predictions)
    if any(not math.isfinite(v) or v < 0 for v in flat):
        raise ValueError("HGB produced invalid visits")
    size = len(history.sku_ids)
    return tuple(flat[i : i + size] for i in range(0, len(flat), size))


def predict_hgb(
    history: ForecastHistory,
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...], float, float]:
    started = process_time()
    validation = _fit_predict(history, 42, tuple(range(42, 56)))
    validation_cpu = process_time() - started
    started = process_time()
    final = _fit_predict(history, 56, (56,))[0]
    return validation, final, validation_cpu, process_time() - started
