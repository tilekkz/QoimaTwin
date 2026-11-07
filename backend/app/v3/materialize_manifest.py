"""Deterministic review artifact; regeneration recompiles the pinned source package."""

from __future__ import annotations

import json
from dataclasses import asdict
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.v3.profile import CompiledManualInputs


def _exact_json(value: object) -> object:
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, frozenset):
        return sorted(value)
    raise TypeError(f"unsupported materialized value: {type(value).__name__}")


def materialized_bytes(inputs: CompiledManualInputs) -> bytes:
    """Serialize every frozen execution choice, including inactive authoritative stock."""
    value = {
        "schema": "synthetic-v3-manual-materialized-v1",
        "input_hash": inputs.input_hash,
        "horizon_tick": inputs.horizon_tick,
        "end_tick": inputs.end_tick,
        "graph_derivation": "pinned layout-links plus proposal's validated connector polylines",
        "profile": asdict(inputs.profile),
    }
    return (
        json.dumps(
            value, default=_exact_json, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")
