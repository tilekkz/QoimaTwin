"""Lossless public checkpoint transport: periodic full state plus absolute stock updates."""

from collections.abc import Iterable, Iterator
from copy import deepcopy
from typing import Any

from app.storage.canonical_json import sha256_hex

type Json = dict[str, Any]
type StockKey = tuple[str, str, str, str]
TRANSPORT_KEYS = {"encoding", "base_at_s", "base_state_hash", "full_base_at_s"}


def _balances(rows: list[list[Any]]) -> dict[StockKey, int]:
    balances: dict[StockKey, int] = {}
    for row in rows:
        if len(row) != 5 or any(not isinstance(value, str) for value in row[:4]):
            raise ValueError("invalid checkpoint balance row")
        quantity = row[4]
        if type(quantity) is not int or quantity < 0:
            raise ValueError("checkpoint balances must be nonnegative integer quantities")
        key = (row[0], row[1], row[2], row[3])
        if key in balances:
            raise ValueError("duplicate checkpoint balance key")
        balances[key] = quantity
    return balances


def encode_snapshots(snapshots: Iterable[Json], *, full_every: int = 10) -> Iterator[Json]:
    """Emit one checkpoint at a time; other public state fields remain fully present."""
    if type(full_every) is not int or full_every <= 0:
        raise ValueError("full checkpoint period must be a positive integer")
    previous: Json | None = None
    prior_balances: dict[StockKey, int] = {}
    full_base: float = 0
    for index, snapshot in enumerate(snapshots):
        balances = _balances(snapshot["state"]["ledger"]["balances"])
        if previous is not None and snapshot["at_tick"] <= previous["at_tick"]:
            raise ValueError("checkpoint times must increase")
        full = (
            index % full_every == 0 or list(balances) != sorted(balances) or 0 in balances.values()
        )
        if full:
            full_base = snapshot["at_s"]
        compact = deepcopy(snapshot)
        compact.update(
            encoding="full" if full else "delta",
            base_at_s=None if full or previous is None else previous["at_s"],
            base_state_hash=None if full or previous is None else previous["state_hash"],
            full_base_at_s=full_base,
        )
        if not full:
            ledger = compact["state"]["ledger"]
            del ledger["balances"]
            ledger["balances_delta"] = [
                [*key, balances.get(key, 0)]
                for key in sorted(balances.keys() | prior_balances.keys())
                if balances.get(key) != prior_balances.get(key)
            ]
        yield compact
        previous, prior_balances = snapshot, balances


def _delta_balances(compact: Json, previous: Json | None) -> list[list[Any]]:
    if previous is None:
        raise ValueError("delta checkpoint requires its decoded previous checkpoint")
    if (
        compact["base_at_s"] != previous["at_s"]
        or compact["base_state_hash"] != previous["state_hash"]
        or sha256_hex(previous["state"]) != previous["state_hash"]
        or compact["at_tick"] <= previous["at_tick"]
    ):
        raise ValueError("delta checkpoint base mismatch")
    balances = _balances(previous["state"]["ledger"]["balances"])
    for key, quantity in _balances(compact["state"]["ledger"]["balances_delta"]).items():
        if quantity:
            balances[key] = quantity
        else:
            balances.pop(key, None)
    return [[*key, quantity] for key, quantity in sorted(balances.items())]


def decode_snapshot(compact: Json, previous: Json | None) -> Json:
    """Return the original public snapshot and verify its full-state hash and delta base."""
    encoding = compact.get("encoding")
    if encoding not in {"full", "delta"}:
        raise ValueError("unknown checkpoint encoding")
    decoded = deepcopy({key: value for key, value in compact.items() if key not in TRANSPORT_KEYS})
    ledger = decoded["state"]["ledger"]
    if encoding == "delta":
        ledger["balances"] = _delta_balances(compact, previous)
        del ledger["balances_delta"]
    else:
        if compact.get("base_at_s") is not None or compact.get("base_state_hash") is not None:
            raise ValueError("full checkpoint cannot have a previous base")
        _balances(ledger["balances"])
    if sha256_hex(decoded["state"]) != decoded["state_hash"]:
        raise ValueError("checkpoint decoded state hash mismatch")
    return decoded
