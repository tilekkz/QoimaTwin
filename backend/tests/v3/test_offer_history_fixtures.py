"""Declared synthetic whole-HU offers, independent of C10 unclocked intensities."""

from datetime import date, timedelta

import pytest

from app.v3.offer_history import compile_offer_history
from app.v3.offer_history_models import OfferHistoryChoices, OfferHistoryInputs, OfferProvenance

DAY = date(2026, 11, 9)


def choices(day: date = DAY) -> OfferHistoryChoices:
    return OfferHistoryChoices(
        "outbound_whole_hu_offers",
        day,
        "Etc/UTC",
        9 * 3600,
        17 * 3600,
        OfferProvenance("declared_synthetic", "constant-fixture", "hand-constants", "1", None),
    )


def history_bytes(first: int = 1, second: int = 3, day: date = DAY, *, rest: int = 0) -> bytes:
    rows = ["date,sku_id,offered_hus"]
    for offset in range(56):
        observed = day - timedelta(days=56 - offset)
        for sku in range(1, 201):
            count = first if sku == 1 else second if sku == 2 else rest
            rows.append(f"{observed.isoformat()},DEMO_{sku:03d},{count}")
    return ("\n".join(rows) + "\n").encode()


@pytest.fixture(scope="module")
def history() -> OfferHistoryInputs:
    return compile_offer_history(history_bytes(), choices())
