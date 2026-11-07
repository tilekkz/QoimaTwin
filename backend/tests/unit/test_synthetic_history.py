"""History includes every calendar day and SKU, with exact daily order budgets."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from numpy.random import Generator

from app.contracts.scenario import Order, OrderLine
from app.data import history
from app.data.catalog import SKU_IDS
from app.data.orders import iter_orders


@pytest.mark.slow
def test_fresh_history_generation_matches_shared_immutable_input(synthetic_history: Any) -> None:
    assert history.generate_history().equals(synthetic_history)


def test_history_daily_counts_and_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    counts: list[tuple[int, int, int]] = []

    def counted(
        rng: Generator,
        weights: tuple[float, ...],
        orders_per_hour: int,
        horizon_s: int,
        id_prefix: str,
    ) -> Iterator[Order]:
        count = visits = units = 0
        for order in iter_orders(rng, weights, orders_per_hour, horizon_s, id_prefix):
            count += 1
            visits += len(order.lines)
            units += order.units
            yield order
        counts.append((count, visits, units))

    monkeypatch.setattr(history, "iter_orders", counted)
    table = history.generate_history()
    assert len(table) == 56 * 200
    assert len(counts) == 56
    assert table.groupby("split")["date"].nunique().to_dict() == {"train": 42, "validation": 14}
    assert table["date"].min() == history.TEST_DAY - timedelta(days=56)
    assert table["date"].max() == history.TEST_DAY - timedelta(days=1)
    assert history.TEST_DAY.weekday() == 0
    for offset, (count, visits, units) in enumerate(counts):
        day = history.TEST_DAY - timedelta(days=56 - offset)
        rows = table[table["date"] == day]
        assert count == (1344 if day.weekday() >= 5 else 1920)
        assert tuple(rows["sku_id"]) == SKU_IDS
        assert rows["visits"].sum() == visits
        assert rows["units"].sum() == units
        assert rows["split"].unique().tolist() == ["train" if offset < 42 else "validation"]


def test_history_zero_fills_absent_skus(monkeypatch: pytest.MonkeyPatch) -> None:
    def sparse(
        rng: Generator,
        weights: tuple[float, ...],
        orders_per_hour: int,
        horizon_s: int,
        id_prefix: str,
    ) -> Iterator[Order]:
        yield Order(order_id="H", arrival_s=1.0, lines=(OrderLine(sku_id="DEMO_001", quantity=3),))

    monkeypatch.setattr(history, "iter_orders", sparse)
    table = history.generate_history()
    absent = table[table["sku_id"] != "DEMO_001"]
    assert len(absent) == 56 * 199
    assert absent["visits"].eq(0).all()
    assert absent["units"].eq(0).all()
    assert table["units"].sum() == 56 * 3
