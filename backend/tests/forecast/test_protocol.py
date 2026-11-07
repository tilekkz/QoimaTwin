"""Manual forecast oracles and strict temporal inputs."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.forecast import fit_forecast, from_rows

DAY = date(2026, 11, 9)
SKUS = ("A", "B")


def rows() -> list[dict[str, object]]:
    return [
        {"date": DAY - timedelta(days=56 - i), "sku_id": sku, "visits": i + 1}
        for i in range(56)
        for sku in SKUS
    ]


def test_mean28_manual_and_aggregate_wape() -> None:
    snapshot = fit_forecast(from_rows(rows(), test_day=DAY, sku_ids=SKUS))
    assert snapshot.predictions.visits_by_sku == {"A": 42.5, "B": 42.5}
    assert snapshot.training_visits_by_sku == {"A": 21.5, "B": 21.5}
    # Every rolling prediction trails the increasing target by 14.5.
    # Final14 targets sum to (43+56)*14/2 = 693 per SKU.
    assert snapshot.validation.absolute_error == 14 * 14.5 * 2
    assert snapshot.validation.actual_visits == 693 * 2
    assert snapshot.validation.wape == pytest.approx(406 / 1386)
    assert snapshot.validation.target_rows == 28
    assert snapshot.cutoff == DAY - timedelta(days=1)
    assert snapshot.test_day == DAY
    assert snapshot.synthetic_training is True


def test_order_immutability_and_timing_identity() -> None:
    history = from_rows(rows(), test_day=DAY, sku_ids=reversed(SKUS))
    snapshot = fit_forecast(history)
    other = fit_forecast(from_rows(list(reversed(rows())), test_day=DAY, sku_ids=SKUS))
    assert snapshot.semantic_id == other.semantic_id
    assert hash(snapshot)
    document = snapshot.to_dict()
    document["model"] = "changed"
    assert snapshot.to_dict()["model"] == "mean28"
    with pytest.raises(TypeError):
        snapshot.predictions.visits_by_sku["A"] = 0  # type: ignore[index]


@pytest.mark.parametrize("value", [-1, math.inf, math.nan, True, "garbage"])
def test_invalid_visits(value: object) -> None:
    source = rows()
    source[0]["visits"] = value
    with pytest.raises(ValueError):
        from_rows(source, test_day=DAY, sku_ids=SKUS)


def test_missing_duplicate_future_and_wrong_split() -> None:
    for source in (rows()[:-1], rows() + rows()[:1]):
        with pytest.raises(ValueError):
            from_rows(source, test_day=DAY, sku_ids=SKUS)
    source = rows()
    source[-1]["date"] = DAY
    with pytest.raises(ValueError):
        from_rows(source, test_day=DAY, sku_ids=SKUS)
    source = rows()
    source[0]["split"] = "validation"
    with pytest.raises(ValueError):
        from_rows(source, test_day=DAY, sku_ids=SKUS)


def test_zero_denominator() -> None:
    source = rows()
    for row in source:
        row["visits"] = 0
    snapshot = fit_forecast(from_rows(source, test_day=DAY, sku_ids=SKUS))
    assert snapshot.validation.wape is None
    assert snapshot.predictions.visits_by_sku == {"A": 0, "B": 0}
