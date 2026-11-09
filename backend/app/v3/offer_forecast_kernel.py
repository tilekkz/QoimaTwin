"""Reuse fixed numerical kernels with explicit source/date; never legacy semantic IDs."""

import math
import platform
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import cast

from app.forecast.artifact import Model
from app.forecast.fit import fit_forecast
from app.forecast.history import ForecastHistory
from app.v3.offer_forecast_models import OfferForecastCPU, OfferForecastEvaluation, Predictions
from app.v3.offer_history_models import OfferHistoryInputs


def exact(value: float) -> Fraction:
    if type(value) is not float or not math.isfinite(value) or value < 0:
        raise ValueError("Numerical kernel must return a finite nonnegative binary64 value")
    return Fraction(value)


def validate_cpu(value: OfferForecastCPU) -> None:
    if type(value) is not OfferForecastCPU:
        raise ValueError("Exact CPU observation required")
    for elapsed in (value.total_s, value.validation_s, value.final_fit_s):
        exact(elapsed)


def identity() -> tuple[tuple[str, str], ...]:
    app = Path(__file__).resolve().parents[1]
    paths = ["forecast/history.py", "forecast/fit.py", "forecast/hgb.py", "forecast/artifact.py"]
    paths.extend(
        p.relative_to(app).as_posix() for p in sorted((app / "v3").glob("offer_forecast*.py"))
    )
    rows = [(path, sha256((app / path).read_bytes()).hexdigest()) for path in paths]
    rows.extend(
        ("package/" + name, version(name)) for name in ("numpy", "scikit-learn", "threadpoolctl")
    )
    rows.append(("python", platform.python_version()))
    return tuple(sorted(rows))


def calculate(
    history: OfferHistoryInputs, model: str
) -> tuple[Predictions, Predictions, OfferForecastEvaluation, OfferForecastCPU]:
    if type(model) is not str or model not in {"mean28", "hgb"}:
        raise ValueError("Explicit mean28 or hgb model required")
    grid = ForecastHistory(
        history.choices.test_day,
        history.sku_ids,
        tuple(tuple(float(v) for v in row) for row in history.counts),
        True,
        history.raw_history_sha256,
    )
    output = fit_forecast(grid, cast(Model, model))
    predicted = tuple((sku, exact(v)) for sku, v in output.predictions.values)
    baseline = tuple((sku, exact(v)) for sku, v in output.training_baseline.values)
    if (
        tuple(sku for sku, _ in predicted) != history.sku_ids
        or tuple(s for s, _ in baseline) != history.sku_ids
    ):
        raise ValueError("Kernel must preserve the complete source SKU set")
    evaluation = output.validation
    absolute = exact(evaluation.absolute_error)
    actual = Fraction(sum(sum(row) for row in history.counts[42:]))
    facts = OfferForecastEvaluation(
        absolute,
        actual,
        absolute / actual if actual else None,
        evaluation.target_rows,
        evaluation.fit_target_rows,
        28 * len(history.sku_ids),
        evaluation.first_day.isoformat(),
        evaluation.last_day.isoformat(),
    )
    cpu = OfferForecastCPU(
        output.cpu_time_s, output.validation_cpu_time_s, output.final_fit_cpu_time_s
    )
    validate_cpu(cpu)
    return predicted, baseline, facts, cpu
