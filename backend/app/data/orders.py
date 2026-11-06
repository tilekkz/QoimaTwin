"""Evenly spaced orders and a frozen NumPy draw protocol.

Per order: rng.integers(2, 5), rng.choice(200, size=k, replace=False, p=weights),
then rng.integers(1, 5) once per selected SKU in NumPy selection order. Only after
assigning quantities are lines sorted by sku_id. No vectorized quantity draws.
The passed generator advances intentionally; weights remain unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from fractions import Fraction

from numpy.random import Generator

from app.contracts.scenario import Order, OrderLine
from app.data.catalog import SKU_IDS, normalize_weights


def _lines(rng: Generator, weights: tuple[float, ...]) -> tuple[OrderLine, ...]:
    k = int(rng.integers(2, 5))
    selected = rng.choice(200, size=k, replace=False, p=weights)
    lines = (
        OrderLine(sku_id=SKU_IDS[int(index)], quantity=int(rng.integers(1, 5)))
        for index in selected
    )
    return tuple(sorted(lines, key=lambda line: line.sku_id))


def iter_orders(
    rng: Generator,
    weights: tuple[float, ...],
    orders_per_hour: int,
    horizon_s: int,
    id_prefix: str,
) -> Iterator[Order]:
    """Stream orders; float(exact Fraction) rounds once if a rate is non-dyadic.

    Rates 240, 600 and history's 168 have no accumulated float error. The first
    two are exactly representable; 168 uses the nearest float of the rational.
    """
    if type(horizon_s) is not int or horizon_s < 0 or horizon_s % 3600:
        raise ValueError("horizon_s must be a nonnegative whole number of hours")
    if type(orders_per_hour) is not int or orders_per_hour <= 0:
        raise ValueError("orders_per_hour must be a positive integer")
    normalize_weights(weights)  # Validate without changing the supplied probabilities.
    if sum(weight > 0 for weight in weights) < 4:
        raise ValueError("at least four SKUs must have positive sampling weight")
    for hour in range(horizon_s // 3600):
        for i in range(orders_per_hour):
            arrival = Fraction(hour * 3600) + Fraction((2 * i + 1) * 1800, orders_per_hour)
            index = hour * orders_per_hour + i
            yield Order(
                order_id=f"{id_prefix}{index:06d}",
                arrival_s=float(arrival),
                lines=_lines(rng, weights),
            )


def generate_orders(
    rng: Generator,
    weights: tuple[float, ...],
    orders_per_hour: int,
    horizon_s: int,
    id_prefix: str,
) -> tuple[Order, ...]:
    return tuple(iter_orders(rng, weights, orders_per_hour, horizon_s, id_prefix))
