"""Fixed SKU ranks and immutable weight vectors, including pre-normalization weights."""

from __future__ import annotations

import math
from dataclasses import dataclass

SKU_IDS = tuple(f"DEMO_{rank:03d}" for rank in range(1, 201))


@dataclass(frozen=True, slots=True)
class Catalog:
    sku_ids: tuple[str, ...]
    original_weights: tuple[float, ...]
    normalized_weights: tuple[float, ...]


def normalize_weights(weights: tuple[float, ...]) -> tuple[float, ...]:
    """Validate the catalog's sampling vector and return a fresh normalized tuple."""
    if len(weights) != len(SKU_IDS):
        raise ValueError("weights must contain exactly 200 values")
    if any(not math.isfinite(value) or value < 0 for value in weights):
        raise ValueError("weights must be finite and nonnegative")
    total = math.fsum(weights)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("weight total must be finite and positive")
    return tuple(value / total for value in weights)


def build_catalog() -> Catalog:
    original = tuple(rank**-0.9 for rank in range(1, 201))
    return Catalog(SKU_IDS, original, normalize_weights(original))


def multiplied_weights(
    base: tuple[float, ...], sku: str = "DEMO_173", multiplier: float = 5
) -> tuple[float, ...]:
    """Preserve other weights exactly before normalization; never mutate base."""
    normalize_weights(base)
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("multiplier must be finite and positive")
    index = SKU_IDS.index(sku)
    return tuple(weight * multiplier if i == index else weight for i, weight in enumerate(base))


def promotion_weights(
    base: tuple[float, ...], sku: str = "DEMO_173", multiplier: float = 5
) -> tuple[float, ...]:
    return normalize_weights(multiplied_weights(base, sku, multiplier))
