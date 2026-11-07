"""Exact Hamilton allocation with stable lexical SKU/port ties and explicit deltas."""

from fractions import Fraction

from app.v3.workload_models import DemandWeight, Quota


def validate_weights(weights: tuple[DemandWeight, ...], offered: int) -> None:
    if type(offered) is not int or offered < 0 or type(weights) is not tuple:
        raise ValueError("Whole-HU budget must be a nonnegative integer; weights immutable")
    keys = []
    for row in weights:
        if not isinstance(row, DemandWeight):
            raise ValueError("Typed demand weights required")
        if any(type(value) is not str or not value.strip() for value in (row.sku_id, row.port_id)):
            raise ValueError("Demand weights require explicit SKU and port IDs")
        if type(row.weight) is not Fraction or row.weight < 0:
            raise ValueError("Demand weights must be exact nonnegative fractions")
        keys.append((row.sku_id, row.port_id))
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate SKU/port demand weight")
    if offered and sum((row.weight for row in weights), Fraction(0)) <= 0:
        raise ValueError("Positive whole-HU budget requires positive total weight")


def allocate_quotas(weights: tuple[DemandWeight, ...], offered: int) -> tuple[Quota, ...]:
    validate_weights(weights, offered)
    rows = sorted(weights, key=lambda row: (row.sku_id, row.port_id))
    total = sum((row.weight for row in rows), Fraction(0))
    expected = [row.weight * offered / total if total else Fraction(0) for row in rows]
    counts = [value.numerator // value.denominator for value in expected]
    order = sorted(
        range(len(rows)),
        key=lambda i: (-(expected[i] - counts[i]), rows[i].sku_id, rows[i].port_id),
    )
    for index in order[: offered - sum(counts)]:
        counts[index] += 1
    return tuple(
        Quota(row.sku_id, row.port_id, expected[i], counts[i], counts[i] - expected[i])
        for i, row in enumerate(rows)
    )
