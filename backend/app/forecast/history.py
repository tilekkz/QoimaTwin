"""Strict immutable demand grid; no scenario or future order access."""

from __future__ import annotations

import csv
import hashlib
import io
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from app.data.catalog import SKU_IDS
from app.data.history import TEST_DAY
from app.storage.canonical_json import canonical_bytes


@dataclass(frozen=True, slots=True)
class ForecastHistory:
    test_day: date
    sku_ids: tuple[str, ...]
    visits: tuple[tuple[float, ...], ...]  # day-major, then sorted SKU
    synthetic_training: bool = True
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sku_ids", tuple(self.sku_ids))
        object.__setattr__(self, "visits", tuple(tuple(_number(v) for v in r) for r in self.visits))
        if type(self.test_day) is not date or type(self.synthetic_training) is not bool:
            raise ValueError("expected calendar test_day and boolean synthetic_training")
        if not self.sku_ids or tuple(sorted(set(self.sku_ids))) != self.sku_ids:
            raise ValueError("SKU IDs must be nonempty, sorted and unique")
        if any(not isinstance(s, str) or not s for s in self.sku_ids):
            raise ValueError("SKU IDs must be nonempty strings")
        if len(self.visits) != 56 or any(len(row) != len(self.sku_ids) for row in self.visits):
            raise ValueError("history must contain exactly 56 complete days")

    @property
    def history_hash(self) -> str:
        return hashlib.sha256(
            canonical_bytes(
                {
                    "protocol": "qoima-history-visits-1",
                    "test_day": self.test_day.isoformat(),
                    "sku_ids": self.sku_ids,
                    "visits": self.visits,
                }
            )
        ).hexdigest()


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("visits/units must be finite nonnegative numbers")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("visits/units must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("visits/units must be finite and nonnegative")
    return 0.0 if result == 0 else result


def _day(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be an ISO calendar date") from exc
        if value == parsed.isoformat():
            return parsed
    raise ValueError("date must be a calendar date without a time")


def from_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    test_day: date = TEST_DAY,
    sku_ids: Iterable[str] = SKU_IDS,
    synthetic_training: bool = True,
) -> ForecastHistory:
    """Require all 56 days and expected SKUs; optional units/split are validated."""
    skus = tuple(sorted(sku_ids))
    values: dict[tuple[int, str], float] = {}
    for row in rows:
        if not {"date", "sku_id", "visits"} <= row.keys():
            raise ValueError("missing date, sku_id or visits")
        day, sku = _day(row["date"]), row["sku_id"]
        offset = (day - test_day).days + 56
        if not 0 <= offset < 56 or not isinstance(sku, str) or sku not in skus:
            raise ValueError("wrong SKU/date grid or future leakage")
        key = (offset, sku)
        if key in values:
            raise ValueError("duplicate SKU/date row")
        if "split" in row and row["split"] != ("train" if offset < 42 else "validation"):
            raise ValueError("split disagrees with temporal boundary")
        if "units" in row:
            _number(row["units"])
        values[key] = _number(row["visits"])
    if len(values) != 56 * len(skus):
        raise ValueError("missing SKU/date rows")
    matrix = tuple(tuple(values[i, sku] for sku in skus) for i in range(56))
    return ForecastHistory(test_day, skus, matrix, synthetic_training)


def read_csv(
    path: str | Path,
    *,
    test_day: date = TEST_DAY,
    sku_ids: Iterable[str] = SKU_IDS,
    synthetic_training: bool = True,
) -> ForecastHistory:
    """Normalize demand identity; retain exact source byte hash separately."""
    payload = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("missing or duplicate CSV headers")
    rows: list[dict[str, object]] = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("wrong CSV row width")
        rows.append(dict(row))
    history = from_rows(
        rows, test_day=test_day, sku_ids=sku_ids, synthetic_training=synthetic_training
    )
    return ForecastHistory(
        history.test_day,
        history.sku_ids,
        history.visits,
        history.synthetic_training,
        hashlib.sha256(payload).hexdigest(),
    )


def target_day(history: ForecastHistory, offset: int) -> date:
    return history.test_day - timedelta(days=56 - offset)
