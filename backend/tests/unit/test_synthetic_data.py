"""Sampling protocol, independent streams, arrivals and promotion provenance."""

from __future__ import annotations

from fractions import Fraction

import pytest
from numpy.random import PCG64, Generator, SeedSequence

from app.data.catalog import SKU_IDS, build_catalog, multiplied_weights, promotion_weights
from app.data.orders import generate_orders
from app.data.receipts import generate_receipts
from app.data.seeds import HISTORY, ORDERS, RECEIPTS, stream_rng


def test_streams_match_explicit_seed_sequence_and_are_independent() -> None:
    samples = []
    for code in (HISTORY, ORDERS, RECEIPTS):
        expected = Generator(PCG64(SeedSequence([20261107, code]))).integers(0, 1000, size=20)
        actual = stream_rng(code).integers(0, 1000, size=20)
        assert actual.tolist() == expected.tolist()
        samples.append(actual.tolist())
    assert samples[0] != samples[1] != samples[2]
    assert stream_rng(ORDERS, 99).integers(0, 1000, size=20).tolist() != samples[1]


def test_catalog_and_promotion() -> None:
    catalog = build_catalog()
    base = catalog.normalized_weights
    before = tuple(base)
    assert catalog.sku_ids == tuple(f"DEMO_{i:03d}" for i in range(1, 201))
    assert catalog.original_weights == tuple(i**-0.9 for i in range(1, 201))
    boosted = multiplied_weights(base)
    normalized = promotion_weights(base)
    assert base == before
    assert sum(base) == pytest.approx(1)
    assert sum(normalized) == pytest.approx(1)
    assert normalized[172] == pytest.approx(5 * base[172] / (1 - base[172] + 5 * base[172]))
    assert all(boosted[i] == base[i] for i in range(200) if i != 172)
    assert boosted[172] == base[172] * 5


def test_draw_order_matches_scalar_reference() -> None:
    weights = build_catalog().normalized_weights
    orders = generate_orders(stream_rng(ORDERS), weights, 240, 3600, "T")
    reference = stream_rng(ORDERS)
    for index, order in enumerate(orders):
        k = int(reference.integers(2, 5))
        selected = reference.choice(200, size=k, replace=False, p=weights)
        expected = sorted((SKU_IDS[int(i)], int(reference.integers(1, 5))) for i in selected)
        assert [(line.sku_id, line.quantity) for line in order.lines] == expected
        assert order.order_id == f"T{index:06d}"
    assert orders[0].arrival_s == 7.5


@pytest.mark.parametrize("rate", [240, 600, 168, 7])
def test_arrivals_come_from_exact_rational(rate: int) -> None:
    orders = generate_orders(
        stream_rng(ORDERS), build_catalog().normalized_weights, rate, 7200, "T"
    )
    for index, order in enumerate(orders):
        hour, i = divmod(index, rate)
        exact = Fraction(hour * 3600) + Fraction((2 * i + 1) * 1800, rate)
        assert order.arrival_s == float(exact)
        if rate in (240, 600):
            assert Fraction(order.arrival_s) == exact
    assert orders[-1].arrival_s < 7200


@pytest.mark.parametrize("horizon", [-3600, 1, 3599, 3601])
def test_orders_reject_invalid_horizon(horizon: int) -> None:
    with pytest.raises(ValueError, match="whole number of hours"):
        generate_orders(stream_rng(ORDERS), build_catalog().normalized_weights, 240, horizon, "T")


def test_receipts_boundaries_cycle_and_ids() -> None:
    assert generate_receipts(90) == ()
    assert len(generate_receipts(91)) == 1
    receipts = generate_receipts(11 * 3600)
    for i, receipt in enumerate(receipts):
        assert receipt.arrival_s == (i + 0.5) * 180
        assert receipt.receipt_id == f"RCP{i:05d}"
        assert receipt.sku_id == SKU_IDS[i % 200]
        assert receipt.quantity == 500
