"""Frozen synthetic history: 56 days, with one order alive at a time."""

from __future__ import annotations

from datetime import date, timedelta

# The offline project environment has pandas but not the optional pandas-stubs.
import pandas as pd  # type: ignore[import-untyped]

from app.data.catalog import SKU_IDS, build_catalog
from app.data.orders import iter_orders
from app.data.seeds import HISTORY, stream_rng

TEST_DAY = date(2026, 11, 9)
HISTORY_DAYS = 56
TRAIN_DAYS = 42


def daily_order_count(day: date) -> int:
    return 1344 if day.weekday() >= 5 else 1920


def generate_history() -> pd.DataFrame:
    """Aggregate baseline demand over eight hours/day (240/h or 168/h weekends).

    Columns: date, sku_id, visits, units, split. Dates are calendar date objects;
    every day has all 200 SKUs, even if no order selected one of them.
    """
    rng = stream_rng(HISTORY)
    weights = build_catalog().normalized_weights
    rows: list[tuple[date, str, int, int, str]] = []
    indices = {sku: index for index, sku in enumerate(SKU_IDS)}
    for offset in range(HISTORY_DAYS):
        day = TEST_DAY - timedelta(days=HISTORY_DAYS - offset)
        visits, units = [0] * 200, [0] * 200
        orders = iter_orders(rng, weights, daily_order_count(day) // 8, 8 * 3600, "HST")
        for order in orders:
            for line in order.lines:
                index = indices[line.sku_id]
                visits[index] += 1
                units[index] += line.quantity
        split = "train" if offset < TRAIN_DAYS else "validation"
        rows.extend((day, sku, visits[i], units[i], split) for i, sku in enumerate(SKU_IDS))
    return pd.DataFrame(rows, columns=["date", "sku_id", "visits", "units", "split"])
