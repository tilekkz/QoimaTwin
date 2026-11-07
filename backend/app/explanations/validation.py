"""Shared scalar checks at the trusted comparison-artifact boundary."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import cast

from app.explanations.errors import ExplanationError
from app.explanations.models import Fact


def mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExplanationError("invalid_facts")
    return cast(Mapping[str, object], value)


def number(source: Mapping[str, object], name: str, prefix: str = "") -> Fact:
    value = source.get(name)
    if type(value) not in (int, float):
        raise ExplanationError("invalid_facts")
    numeric = cast(int | float, value)
    try:
        finite = math.isfinite(numeric)
    except OverflowError:
        finite = False
    if not finite:
        raise ExplanationError("invalid_facts")
    return Fact(fact_id=f"{prefix}{name}", value=numeric)
