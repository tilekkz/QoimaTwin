"""Boundary rejection, source identity and aggregate rather than SKU-mean WAPE."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.forecast import ForecastHistory, Predictions, fit_forecast, from_rows, read_csv

DAY = date(2026, 11, 9)


def source() -> list[dict[str, Any]]:
    return [
        {"date": DAY - timedelta(days=56 - i), "sku_id": sku, "visits": i + 1 if sku == "A" else 1}
        for i in range(56)
        for sku in ("A", "B")
    ]


def test_unequal_sku_aggregate_wape_and_nested_copy() -> None:
    snapshot = fit_forecast(from_rows(source(), test_day=DAY, sku_ids=("A", "B")))
    # A has 14*14.5 absolute error / 693 actual, B has 0 error /14 actual.
    assert snapshot.validation.wape == pytest.approx(203 / 707)
    document = snapshot.to_dict()
    predictions = document["predictions"]
    assert isinstance(predictions, dict)
    predictions["visits_by_sku"]["A"] = 999
    assert snapshot.predictions.visits_by_sku["A"] == 42.5
    with pytest.raises(FrozenInstanceError):
        snapshot.model = "hgb"  # type: ignore[misc]


def test_direct_constructors_defensively_freeze() -> None:
    values: Any = [[1.0]] * 56
    history = ForecastHistory(DAY, ("A",), values)
    before = history.history_hash
    values[0][0] = 9
    assert history.history_hash == before
    predictions: Any = [["A", 1.0]]
    artifact = Predictions(predictions)
    predictions[0][1] = 9
    assert artifact.visits_by_sku["A"] == 1
    assert hash(history) and hash(artifact)


def test_csv_roundtrip_and_source_hash(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["date", "sku_id", "visits"])
        writer.writeheader()
        writer.writerows(source())
    history = read_csv(path, test_day=DAY, sku_ids=("A", "B"))
    assert (
        history.history_hash == from_rows(source(), test_day=DAY, sku_ids=("A", "B")).history_hash
    )
    assert history.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    for text in (
        "date,date,visits\n",
        "date,sku_id,visits\n2026-10-01,A,1,extra\n",
        "date,sku_id,visits\n2026-10-01,A\n",
        "date,sku_id,visits\n2026-10-01,A,nan\n",
    ):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            read_csv(path, test_day=DAY, sku_ids=("A", "B"))


def test_complete_sku_and_calendar_grid_required() -> None:
    for data in (
        [r for r in source() if r["sku_id"] == "A"],
        [{k: v for k, v in r.items() if k != "visits"} for r in source()],
    ):
        with pytest.raises(ValueError):
            from_rows(data, test_day=DAY, sku_ids=("A", "B"))
    for value in (datetime(2026, 9, 14), "2026-09-14T00:00:00", "20260914"):
        data = source()
        data[0]["date"] = value
        with pytest.raises(ValueError):
            from_rows(data, test_day=DAY, sku_ids=("A", "B"))
