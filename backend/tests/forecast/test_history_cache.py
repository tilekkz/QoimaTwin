"""Cache immutable source bytes, return independently mutable frames."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

import pytest
from numpy.random import Generator

from app.contracts.scenario import Order, OrderLine
from app.data import history


def test_history_cache_bytes_hash_and_defensive_copies(monkeypatch: pytest.MonkeyPatch) -> None:
    def sparse(
        rng: Generator,
        weights: tuple[float, ...],
        orders_per_hour: int,
        horizon_s: int,
        id_prefix: str,
    ) -> Iterator[Order]:
        yield Order(order_id="H", arrival_s=1, lines=(OrderLine(sku_id="DEMO_001", quantity=3),))

    monkeypatch.setattr(history, "iter_orders", sparse)
    history.history_artifact.cache_clear()
    try:
        expected = history.generate_history().to_csv(index=False, lineterminator="\n").encode()
        artifact = history.history_artifact()
        assert artifact.csv_bytes == expected
        assert artifact.sha256 == hashlib.sha256(expected).hexdigest()
        assert history.history_artifact() is artifact
        first = history.history_by_hash(artifact.sha256)
        first.loc[0, "visits"] = 999
        second = history.history_by_hash(artifact.sha256)
        assert second.loc[0, "visits"] == 1
        assert second.to_csv(index=False, lineterminator="\n").encode() == expected
        with pytest.raises(KeyError):
            history.history_by_hash("missing")
    finally:
        history.history_artifact.cache_clear()
