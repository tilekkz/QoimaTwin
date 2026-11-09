"""Base model and numeric helpers shared by all contract models."""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]
Vec3 = tuple[float, float, float]


def _checked_float(token: str) -> float:
    value = float(token)
    if not value == value or value in (float("inf"), float("-inf")):
        raise ValueError(f"number {token} cannot be reconstructed exactly")
    if Fraction(repr(value)) != Fraction(token):
        raise ValueError(f"number {token} cannot be reconstructed exactly")
    return value


def _checked_int(token: str) -> int:
    _checked_float(token)
    return int(token)


def checked_json_loads(text: str | bytes) -> Any:
    """Reject decimal tokens that float fields would silently round before exact()."""
    return json.loads(text, parse_float=_checked_float, parse_int=_checked_int)


class FrozenModel(BaseModel):
    """Immutable, strict contract model: unknown fields, NaN and Infinity are rejected."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        populate_by_name=True,
    )

    @field_validator(
        "open_pallet_count", "relocation_worker_count", mode="before", check_fields=False
    )
    @classmethod
    def _strict_integer_literals(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("requires an integer literal")
        return value

    @classmethod
    def from_json_text(cls, text: str | bytes) -> Self:
        """Validate JSON text in strict JSON mode (JSON arrays map to tuples)."""
        checked_json_loads(text)
        return cls.model_validate_json(text)

    @classmethod
    def from_data(cls, data: Any) -> Self:
        """Validate already-parsed JSON data with the same strict JSON rules as files."""
        return cls.from_json_text(json.dumps(data, allow_nan=True))


def exact(value: float) -> Fraction:
    """Convert a JSON number to an exact Fraction using its shortest decimal representation."""
    return Fraction(repr(value)) if isinstance(value, float) else Fraction(value)


def exact_vec(vec: Vec3) -> tuple[Fraction, Fraction, Fraction]:
    return (exact(vec[0]), exact(vec[1]), exact(vec[2]))
