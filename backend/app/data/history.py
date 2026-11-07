"""Frozen synthetic history: 56 days, with one order alive at a time."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

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


@dataclass(frozen=True, slots=True)
class HistoryArtifact:
    """Exact original CSV bytes: no shared mutable DataFrame is cached."""

    csv_bytes: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.csv_bytes).hexdigest()


@lru_cache(maxsize=1)
def history_artifact() -> HistoryArtifact:
    """Generate the frozen default history once per process; publish by content hash."""
    payload = generate_history().to_csv(index=False, lineterminator="\n").encode("utf-8")
    return HistoryArtifact(payload)


def history_by_hash(artifact_hash: str) -> pd.DataFrame:
    """Resolve the immutable default artifact and decode a defensive copy."""
    artifact = history_artifact()
    if artifact_hash != artifact.sha256:
        raise KeyError(f"unknown history artifact: {artifact_hash}")
    frame = pd.read_csv(io.BytesIO(artifact.csv_bytes))
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame
