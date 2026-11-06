"""Base model and numeric helpers shared by all contract models."""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]
Vec3 = tuple[float, float, float]


class FrozenModel(BaseModel):
    """Immutable, strict contract model: unknown fields, NaN and Infinity are rejected."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        populate_by_name=True,
    )

    @classmethod
    def from_json_text(cls, text: str | bytes) -> Self:
        """Validate JSON text in strict JSON mode (JSON arrays map to tuples)."""
        return cls.model_validate_json(text)

    @classmethod
    def from_data(cls, data: Any) -> Self:
        """Validate already-parsed JSON data with the same strict JSON rules as files."""
        return cls.model_validate_json(json.dumps(data, allow_nan=True))


def exact(value: float) -> Fraction:
    """Convert a JSON number to an exact Fraction using its shortest decimal representation."""
    return Fraction(repr(value)) if isinstance(value, float) else Fraction(value)


def exact_vec(vec: Vec3) -> tuple[Fraction, Fraction, Fraction]:
    return (exact(vec[0]), exact(vec[1]), exact(vec[2]))
