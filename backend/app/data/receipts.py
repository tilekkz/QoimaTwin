"""Deterministic receipts; the reserved RECEIPTS stream consumes no random draws."""

from __future__ import annotations

from app.contracts.scenario import Receipt
from app.data.catalog import SKU_IDS


def generate_receipts(horizon_s: int) -> tuple[Receipt, ...]:
    if type(horizon_s) is not int or horizon_s < 0:
        raise ValueError("horizon_s must be a nonnegative integer")
    return tuple(
        Receipt(
            receipt_id=f"RCP{i:05d}",
            arrival_s=float(arrival),
            sku_id=SKU_IDS[i % 200],
            quantity=500,
        )
        for i, arrival in enumerate(range(90, horizon_s, 180))
    )
