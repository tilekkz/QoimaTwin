"""Hand-calculated features, strict lag boundaries and tiny HGB smoke."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import pytest

from app.forecast import fit_forecast, from_rows
from app.forecast.hgb import feature_rows

DAY = date(2026, 11, 9)


def history_rows() -> list[dict[str, object]]:
    return [
        {"date": DAY - timedelta(days=56 - i), "sku_id": sku, "visits": i + 1}
        for i in range(56)
        for sku in ("A", "B")
    ]


def test_features_are_manual_and_strictly_before_target() -> None:
    history = from_rows(history_rows(), test_day=DAY, sku_ids=("A", "B"))
    features = feature_rows(history, (42,))
    # At offset42: lag1=42, lag7=36, lag14=29, lag28=15;
    # previous7=36..42, previous28=15..42; Monday; A one-hot.
    assert features[0] == pytest.approx((42, 36, 29, 15, 39, 28.5, 0, 1, 0))
    source = history_rows()
    for row in source:
        day = row["date"]
        assert isinstance(day, date)
        if day >= DAY - timedelta(days=14):
            row["visits"] = 9999
    changed = from_rows(source, test_day=DAY, sku_ids=("A", "B"))
    assert feature_rows(changed, (42,)) == features
    assert feature_rows(changed, (43,)) != feature_rows(history, (43,))
    assert feature_rows(changed, tuple(range(28, 42))) == feature_rows(
        history, tuple(range(28, 42))
    )
    with pytest.raises(ValueError):
        feature_rows(history, (27,))
    with pytest.raises(ValueError):
        feature_rows(history, (57,))


def test_hgb_smoke_is_finite_and_timing_excluded() -> None:
    history = from_rows(history_rows(), test_day=DAY, sku_ids=("A", "B"))
    snapshot = fit_forecast(history, "hgb")
    assert all(0 <= value < 1000 for value in snapshot.predictions.visits_by_sku.values())
    assert snapshot.validation.fit_target_rows == 28
    assert snapshot.validation.target_rows == 28
    assert snapshot.validation.wape is not None
    assert (
        replace(
            snapshot, cpu_time_s=999, validation_cpu_time_s=99, final_fit_cpu_time_s=9
        ).semantic_id
        == snapshot.semantic_id
    )
    assert snapshot.cpu_time_s >= 0
    shuffled = from_rows(list(reversed(history_rows())), test_day=DAY, sku_ids=("B", "A"))
    assert fit_forecast(shuffled, "hgb").semantic_id == snapshot.semantic_id


def test_hgb_fits_only_train_targets_then_all_history(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.forecast import hgb

    recorded: list[tuple[tuple[int, ...], float]] = []
    parameters: list[dict[str, object]] = []

    class Recorder:
        def __init__(self, **kwargs: object) -> None:
            parameters.append(kwargs)

        def fit(self, x: Any, y: Any) -> None:
            recorded.append((x.shape, float(y.sum())))

        def predict(self, x: Any) -> list[float]:
            return [0.0] * len(x)

    monkeypatch.setattr(hgb, "HistGradientBoostingRegressor", Recorder)
    history = from_rows(history_rows(), test_day=DAY, sku_ids=("A", "B"))
    fit_forecast(history, "hgb")
    assert recorded == [((28, 9), 994), ((56, 9), 2380)]
    assert (
        parameters
        == [
            {
                "loss": "poisson",
                "max_iter": 150,
                "max_leaf_nodes": 15,
                "learning_rate": 0.06,
                "l2_regularization": 1.0,
                "random_state": 42,
                "early_stopping": False,
            }
        ]
        * 2
    )


def test_all_zero_hgb_boundary() -> None:
    source = history_rows()
    for row in source:
        row["visits"] = 0
    snapshot = fit_forecast(from_rows(source, test_day=DAY, sku_ids=("A", "B")), "hgb")
    assert snapshot.validation.wape is None
    assert snapshot.predictions.visits_by_sku == {"A": 0, "B": 0}
