"""Exact whole-HU counts on a complete source-SKU/date grid, never implicit zero fill."""

import csv
import io
import re
from datetime import date

from app.v3.offer_history_models import MAX_COUNT


def _cell(row: list[str], day: date, skus: frozenset[str]) -> tuple[int, str, int]:
    if len(row) != 3:
        raise ValueError("Expected date,sku_id,offered_hus cells")
    observed = date.fromisoformat(row[0])
    offset = (observed - day).days + 56
    if observed.isoformat() != row[0] or not 0 <= offset < 56 or row[1] not in skus:
        raise ValueError("Unknown source SKU/date or test-day leakage")
    if re.fullmatch(r"0|[1-9][0-9]{0,15}", row[2]) is None:
        raise ValueError("Canonical nonnegative integer offered-HU count required")
    count = int(row[2])
    if count > MAX_COUNT:
        raise ValueError("Offered-HU count exceeds exact binary64 integer range")
    return offset, row[1], count


def read_counts(raw: bytes, skus: tuple[str, ...], day: date) -> tuple[tuple[int, ...], ...]:
    if type(raw) is not bytes:
        raise ValueError("Exact immutable raw history bytes required")
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        if next(reader, None) != ["date", "sku_id", "offered_hus"]:
            raise ValueError(
                "Whole-HU CSV header required; legacy visits/units is not this measure"
            )
        expected = frozenset(skus)
        values: dict[tuple[int, str], int] = {}
        for row in reader:
            offset, sku, count = _cell(row, day, expected)
            key = offset, sku
            if key in values:
                raise ValueError("Duplicate source SKU/date observation")
            values[key] = count
        if len(values) != 56 * len(skus):
            raise ValueError("Exactly 56 complete observed days required; no zero filling")
        return tuple(tuple(values[i, sku] for sku in skus) for i in range(56))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("Malformed UTF-8 whole-HU CSV") from error
