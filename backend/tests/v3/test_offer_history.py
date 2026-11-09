"""Raw authority, strict grid/window and retained-value controls."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.offer_history import compile_offer_history, load_offer_history, verify_offer_history
from app.v3.offer_history_models import OfferHistoryInputs
from tests.v3.test_offer_history_fixtures import choices, history, history_bytes

__all__ = ["history"]


def test_complete_grid_and_fresh_roundtrip(history: OfferHistoryInputs) -> None:
    fresh = verify_offer_history(history)
    assert fresh == load_offer_history(history.frozen_bytes) == history
    assert fresh is not history and fresh.source is not history.source
    assert len(fresh.sku_ids) == 200 and len(fresh.counts) == 56
    assert fresh.counts[0] == (1, 3, *(0 for _ in range(198)))
    assert fresh.choices.target_unit == "outbound_whole_hu_offers"
    assert fresh.operational_admission is False


def test_raw_identity_differs_but_normalized_demand_is_order_independent(
    history: OfferHistoryInputs,
) -> None:
    lines = history_bytes().splitlines()
    shuffled = b"\n".join([lines[0], *reversed(lines[1:])]) + b"\n"
    other = compile_offer_history(shuffled, choices())
    assert other.raw_history_sha256 != history.raw_history_sha256
    assert other.normalized_history_hash == history.normalized_history_hash
    assert other.input_hash != history.input_hash


@pytest.mark.parametrize("bad", [True, -1, 0.5, "28800"])
def test_exact_window_type_and_eight_hours(bad: Any) -> None:
    with pytest.raises(ValueError):
        compile_offer_history(history_bytes(), replace(choices(), window_end_second=bad))


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "future", "sku", "float", "negative", "legacy"]
)
def test_raw_grid_rejects(change: str) -> None:
    rows = history_bytes().decode().splitlines()
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(rows[1])
    elif change == "future":
        rows[1] = "2026-11-09,DEMO_001,1"
    elif change == "sku":
        rows[1] = rows[1].replace("DEMO_001", "unknown")
    elif change == "legacy":
        rows[0] = "date,sku_id,visits"
    else:
        rows[1] = rows[1].rsplit(",", 1)[0] + (",1.0" if change == "float" else ",-1")
    with pytest.raises(ValueError):
        compile_offer_history(("\n".join(rows) + "\n").encode(), choices())


def test_dst_window_is_not_eight_utc_hours() -> None:
    day = date(2026, 3, 15)
    policy = replace(
        choices(day),
        timezone_name="America/New_York",
        window_start_second=0,
        window_end_second=8 * 3600,
    )
    with pytest.raises(ValueError):
        compile_offer_history(history_bytes(day=day), policy)


def test_retained_and_rehashed_authority_reject(history: OfferHistoryInputs) -> None:
    with pytest.raises(ValueError):
        verify_offer_history(
            replace(history, counts=((True, *history.counts[0][1:]), *history.counts[1:]))
        )
    value = parse_json(history.frozen_bytes)
    value["source"]["source_revision"] = "foreign"
    with pytest.raises(ValueError):
        load_offer_history(canonical_bytes(value))
