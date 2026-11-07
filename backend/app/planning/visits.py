"""Validation and exact conversion of per-SKU visit mappings supplied by the forecast worker."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from fractions import Fraction

from app.planning.errors import PlanningInputError
from app.storage.canonical_json import sha256_hex


def exact_visits(
    visits: Mapping[str, float], skus: Iterable[str], name: str
) -> dict[str, Fraction]:
    """Exact non-negative visits for exactly the given SKU set, sorted by SKU id.

    Floats convert exactly (Fraction of the binary value), so ties and sums are deterministic.
    """
    expected = set(skus)
    missing = sorted(expected - set(visits))
    unknown = sorted(set(visits) - expected)
    if missing or unknown:
        raise PlanningInputError(
            f"{name}: SKU set differs from the assignment; missing {missing[:5]}, "
            f"unknown {unknown[:5]}"
        )
    result: dict[str, Fraction] = {}
    for sku in sorted(visits):
        value = visits[sku]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PlanningInputError(f"{name}[{sku}]: visits must be a number")
        if not math.isfinite(value) or value < 0:
            raise PlanningInputError(f"{name}[{sku}]: visits must be finite and >= 0")
        result[sku] = Fraction(value)
    return result


def visits_hash(visits: Mapping[str, float]) -> str:
    """Canonical hash of a visit mapping; 1 and 1.0 hash the same."""
    return sha256_hex({sku: float(visits[sku]) for sku in sorted(visits)})
