"""Independent nonstationary temporal oracle and strict whole-HU observation boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from fractions import Fraction as F
from pathlib import Path
from time import perf_counter, process_time
from typing import ClassVar

import numpy as np
import pytest
from numpy.typing import NDArray

from app.forecast import hgb
from app.forecast.artifact import ForecastSnapshot, Model
from app.forecast.fit import fit_forecast as numerical_fit
from app.forecast.history import ForecastHistory
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import offer_forecast_kernel
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_forecast_kernel import exact
from app.v3.offer_history import compile_offer_history, load_offer_history, verify_offer_history
from app.v3.offer_history_models import OfferHistoryInputs
from tests.v3.test_offer_history_fixtures import DAY, choices, history, history_bytes

__all__ = ["history"]
type Matrix = NDArray[np.float64]


def _changing_history(*, ramp: bool = False) -> bytes:
    rows = ["date,sku_id,offered_hus"]
    for offset in range(56):
        day = DAY - timedelta(days=56 - offset)
        first = offset + 1 if ramp else (0 if offset < 42 else 28)
        rows.extend(
            f"{day.isoformat()},DEMO_{sku:03d},{first if sku == 1 else 0}" for sku in range(1, 201)
        )
    return ("\n".join(rows) + "\n").encode()


def test_nonstationary_mean_has_rolling_validation_and_fresh_final_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = compile_offer_history(_changing_history(), choices())
    original = numerical_fit

    def measured(data: ForecastHistory, model: Model) -> ForecastSnapshot:
        wall, cpu = perf_counter(), process_time()
        result = original(data, model)
        elapsed, used_cpu = perf_counter() - wall, process_time() - cpu
        print(f"MEAN28_KERNEL_WALL_S={elapsed:.9f} CPU_S={used_cpu:.9f}")
        return result

    monkeypatch.setattr(offer_forecast_kernel, "fit_forecast", measured)
    forecast = fit_offer_forecast(observed, "mean28")
    # Fourteen rolling predictions are 0..13, so error = 14*28 - (0+...+13).
    assert forecast.training_baseline[0] == ("DEMO_001", F(0))
    assert forecast.predictions[0] == ("DEMO_001", F(14))
    assert forecast.evaluation.absolute_error == 301
    assert forecast.evaluation.actual_offers == 392
    assert forecast.evaluation.wape == F(43, 56)
    assert (forecast.evaluation.validation_fit_rows, forecast.evaluation.final_fit_rows) == (
        2800,
        5600,
    )


class _EstimatorSpy:
    instances: ClassVar[list[_EstimatorSpy]] = []

    def __init__(self, **parameters: object) -> None:
        self.parameters = parameters
        self.fit_shape: tuple[int, ...] = ()
        self.target_days: tuple[float, ...] = ()
        self.predict_shape: tuple[int, ...] = ()
        self.first_features: tuple[float, ...] = ()
        self.last_features: tuple[float, ...] = ()
        self.instances.append(self)

    def fit(self, x: Matrix, y: Matrix) -> _EstimatorSpy:
        self.fit_shape = x.shape
        self.target_days = tuple(float(value) for value in y[::200])
        return self

    def predict(self, x: Matrix) -> Matrix:
        self.predict_shape = x.shape
        self.first_features = tuple(float(value) for value in x[0, :6])
        self.last_features = tuple(float(value) for value in x[-200, :6])
        return np.full(x.shape[0], 2.0, dtype=np.float64)


def test_hgb_uses_two_distinct_fits_and_only_prior_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = compile_offer_history(_changing_history(ramp=True), choices())
    _EstimatorSpy.instances = []
    monkeypatch.setattr(hgb, "HistGradientBoostingRegressor", _EstimatorSpy)
    fit_offer_forecast(observed, "hgb")
    validation, final = _EstimatorSpy.instances
    assert validation is not final
    assert validation.fit_shape == (2800, 207) and final.fit_shape == (5600, 207)
    assert validation.target_days == tuple(float(value) for value in range(29, 43))
    assert final.target_days == tuple(float(value) for value in range(29, 57))
    assert validation.predict_shape == (2800, 207) and final.predict_shape == (200, 207)
    assert validation.first_features == (42.0, 36.0, 29.0, 15.0, 39.0, 28.5)
    assert validation.last_features == (55.0, 49.0, 42.0, 28.0, 52.0, 41.5)
    assert final.first_features == (56.0, 50.0, 43.0, 29.0, 53.0, 42.5)
    assert (
        validation.parameters
        == final.parameters
        == {
            "loss": "poisson",
            "max_iter": 150,
            "max_leaf_nodes": 15,
            "learning_rate": 0.06,
            "l2_regularization": 1.0,
            "random_state": 42,
            "early_stopping": False,
        }
    )


def test_observation_ending_exactly_at_test_cutoff_is_not_prior_history() -> None:
    policy = replace(choices(), window_start_second=16 * 3600, window_end_second=24 * 3600)
    with pytest.raises(ValueError, match="before cutoff"):
        compile_offer_history(history_bytes(), policy)


def test_window_changes_semantic_history_even_when_counts_and_raw_bytes_match(
    history: OfferHistoryInputs,
) -> None:
    later = replace(choices(), window_start_second=10 * 3600, window_end_second=18 * 3600)
    shifted = compile_offer_history(history.raw_history, later)
    assert shifted.raw_history_sha256 == history.raw_history_sha256
    assert shifted.counts == history.counts
    assert shifted.normalized_history_hash != history.normalized_history_hash
    assert shifted.input_hash != history.input_hash


def test_largest_exact_binary64_count_is_preserved_and_next_integer_rejects() -> None:
    maximum = 2**53
    observed = compile_offer_history(history_bytes(maximum, 0), choices())
    assert observed.counts[0][0] == maximum
    assert type(observed.counts[0][0]) is int
    with pytest.raises(ValueError, match="exact binary64"):
        compile_offer_history(history_bytes(maximum + 1, 0), choices())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), -1.0, True, 1])
def test_kernel_conversion_rejects_nonfinite_negative_and_scalar_aliases(value: object) -> None:
    with pytest.raises(ValueError):
        exact(value)  # type: ignore[arg-type]


def test_kernel_conversion_preserves_the_actual_binary64_not_rounded_decimal() -> None:
    assert exact(0.1) == F(3602879701896397, 36028797018963968)
    assert exact(0.1) != F(1, 10)


def test_actual_test_stream_is_not_an_allowed_history_wire_field(
    history: OfferHistoryInputs,
) -> None:
    value = parse_json(history.frozen_bytes)
    value["actual_test_stream"] = []
    with pytest.raises(ValueError):
        load_offer_history(canonical_bytes(value))


def test_public_history_rechecks_raw_recipe_authority(
    history: OfferHistoryInputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes
    seen: list[str] = []

    def changed(path: Path) -> bytes:
        raw = original(path)
        if path.name == "cargo-catalog-v3.json":
            seen.append(str(path))
            return raw + b" "
        return raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_offer_history(history)
    assert seen


def test_large_exact_actual_offer_count_keeps_nonzero_wape_denominator() -> None:
    rows = ["date,sku_id,offered_hus"]
    for offset in range(56):
        day = DAY - timedelta(days=56 - offset)
        for sku in range(1, 201):
            count = 2**53 if sku == 1 else int(sku == 2 and offset >= 42)
            rows.append(f"{day.isoformat()},DEMO_{sku:03d},{count}")
    history = compile_offer_history(("\n".join(rows) + "\n").encode(), choices())
    forecast = fit_offer_forecast(history, "mean28")
    # A is predicted exactly; B's rolling errors sum to 14 - (0+...+13)/28.
    actual = 14 * (2**53 + 1)
    assert forecast.evaluation.absolute_error == F(43, 4)
    assert forecast.evaluation.actual_offers == actual
    assert forecast.evaluation.wape == F(43, 4) / actual
