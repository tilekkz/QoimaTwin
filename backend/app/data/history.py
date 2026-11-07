"""Frozen synthetic history: 56 days, with one order alive at a time."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

# The offline project environment has pandas but not the optional pandas-stubs.
import pandas as pd  # type: ignore[import-untyped]

from app.data.catalog import SKU_IDS, build_catalog
from app.data.history_store import HistoryCacheError, load_or_generate
from app.data.orders import iter_orders
from app.data.seeds import HISTORY, MASTER_SEED, stream_rng

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


def history_input_fingerprint() -> str:
    """Source closure and explicit inputs/versions, independent of checkout location."""
    app = Path(__file__).resolve().parents[1]
    sources = (
        "data/history.py",
        "data/history_store.py",
        "data/catalog.py",
        "data/orders.py",
        "data/seeds.py",
        "contracts/scenario.py",
        "contracts/base.py",
    )
    identity = {
        "protocol": "qoima-history-cache-1",
        "source": {name: hashlib.sha256((app / name).read_bytes()).hexdigest() for name in sources},
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "versions": {
            name: version(name) for name in ("numpy", "pandas", "pydantic", "pydantic-core")
        },
        "test_day": TEST_DAY.isoformat(),
        "days": HISTORY_DAYS,
        "train_days": TRAIN_DAYS,
        "seed": MASTER_SEED,
        "stream": HISTORY,
        "catalog": SKU_IDS,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


def history_cache_dir() -> Path:
    """Server-controlled override or private platform cache; never inside this repo."""
    override = os.environ.get("QOIMA_HISTORY_CACHE_DIR")
    if override is not None:
        root = Path(override)
    elif os.name == "nt":
        root = Path.home() / "AppData" / "Local" / "QoimaTwin" / "history-cache-v1"
    else:
        root = Path.home() / ".cache" / "qoimatwin" / "history-cache-v1"
    repo = Path(__file__).resolve().parents[3]
    if not root.is_absolute() or root.resolve().is_relative_to(repo):
        raise HistoryCacheError("invalid history cache directory")
    return root


def _history_csv() -> bytes:
    payload: bytes = generate_history().to_csv(index=False, lineterminator="\n").encode("utf-8")
    return payload


@lru_cache(maxsize=1)
def history_artifact() -> HistoryArtifact:
    """Reuse verified original bytes across processes; retain immutable bytes in memory."""
    payload = load_or_generate(history_cache_dir(), history_input_fingerprint(), _history_csv)
    return HistoryArtifact(payload)


def history_by_hash(artifact_hash: str) -> pd.DataFrame:
    """Resolve the immutable default artifact and decode a defensive copy."""
    artifact = history_artifact()
    if artifact_hash != artifact.sha256:
        raise KeyError(f"unknown history artifact: {artifact_hash}")
    frame = pd.read_csv(io.BytesIO(artifact.csv_bytes))
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame
