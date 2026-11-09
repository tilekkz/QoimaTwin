"""Transport checkpoints preserve exact public state and reject broken delta chains."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.exporter.wire_checkpoint_codec import decode_snapshot, encode_snapshots
from app.storage.canonical_json import canonical_bytes, sha256_hex


def _snapshot(at_s: int, balances: list[list[Any]]) -> dict[str, Any]:
    state = {
        "ledger": {"balances": balances, "reservations": [], "accepted": [], "claims": []},
        "future_field": {"value": at_s},
    }
    return {
        "at_s": at_s,
        "at_tick": at_s * 3_000_000,
        "last_seq": at_s,
        "state_hash": sha256_hex(state),
        "state": state,
    }


def test_delta_quantities_are_absolute_and_zero_deletes_without_mutating_inputs() -> None:
    first = _snapshot(0, [["A", "L", "pickface", "S", 5], ["B", "L", "tote", "T", 3]])
    second = _snapshot(30, [["A", "L", "pickface", "S", 2], ["C", "L", "parcel", "P", 1]])
    original = deepcopy([first, second])
    encoded = list(encode_snapshots([first, second]))
    assert encoded[1]["state"]["ledger"]["balances_delta"] == [
        ["A", "L", "pickface", "S", 2],
        ["B", "L", "tote", "T", 0],
        ["C", "L", "parcel", "P", 1],
    ]
    assert encoded[1]["base_at_s"] == 0
    assert encoded[1]["base_state_hash"] == first["state_hash"]
    assert decode_snapshot(encoded[1], decode_snapshot(encoded[0], None)) == second
    assert [first, second] == original


@pytest.mark.parametrize("damage", ["no_base", "base_time", "base_hash", "state_hash", "encoding"])
def test_bad_delta_chain_is_rejected(damage: str) -> None:
    first, second = _snapshot(0, []), _snapshot(30, [["A", "L", "pickface", "S", 2]])
    encoded = list(encode_snapshots([first, second]))
    compact = encoded[1]
    previous: dict[str, Any] | None = first
    if damage == "no_base":
        previous = None
    elif damage == "base_time":
        compact["base_at_s"] = 1
    elif damage == "base_hash":
        compact["base_state_hash"] = "0" * 64
    elif damage == "state_hash":
        compact["state_hash"] = "0" * 64
    else:
        compact["encoding"] = "unknown"
    with pytest.raises(ValueError):
        decode_snapshot(compact, previous)


def test_full_checkpoints_limit_delta_chain_and_preserve_future_state_fields() -> None:
    snapshots = [_snapshot(i * 30, [["A", "L", "pickface", "S", i + 1]]) for i in range(22)]
    encoded = list(encode_snapshots(snapshots))
    assert [i for i, item in enumerate(encoded) if item["encoding"] == "full"] == [0, 10, 20]
    assert encoded[11]["full_base_at_s"] == 300
    previous = None
    for compact, original in zip(encoded, snapshots, strict=True):
        previous = decode_snapshot(compact, previous)
        assert previous == original


def test_unsorted_or_zero_balance_rows_use_full_checkpoint_without_changing_hash() -> None:
    first = _snapshot(0, [])
    second = _snapshot(30, [["B", "L", "pickface", "S", 1], ["A", "L", "tote", "T", 0]])
    compact = list(encode_snapshots([first, second]))[1]
    assert compact["encoding"] == "full"
    assert decode_snapshot(compact, first) == second


def test_large_static_stock_is_not_repeated_in_every_checkpoint() -> None:
    balances = [[f"S{i:04}", "L", "reserve_slot", "R", 100] for i in range(2000)]
    snapshots = [_snapshot(i * 30, deepcopy(balances)) for i in range(30)]
    encoded = list(encode_snapshots(snapshots))
    assert sum(len(canonical_bytes(item)) for item in encoded) < len(canonical_bytes(snapshots)) / 4
    assert all(
        item["state"]["ledger"]["balances_delta"] == []
        for item in encoded
        if item["encoding"] == "delta"
    )


@pytest.mark.parametrize("period", [0, -1, True, 1.5])
def test_invalid_full_period_is_rejected(period: Any) -> None:
    with pytest.raises(ValueError):
        list(encode_snapshots([], full_every=period))
