"""Strict small JSON decoders for the supported GLB geometry subset."""

from typing import Any, cast

import numpy as np

from app.v3.mesh_proof_types import Array, MeshProofError

Document = dict[str, Any]


def obj(value: object) -> Document:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise MeshProofError("expected JSON object")
    return cast(Document, value)


def items(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise MeshProofError("expected JSON array")
    return value


def integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise MeshProofError("expected bounded integer")
    return value


def vector(value: object, size: int) -> Array:
    values = items(value)
    if len(values) != size or any(type(v) not in (int, float) for v in values):
        raise MeshProofError("invalid numerical vector")
    result = np.asarray(values, dtype=np.float64)
    if not np.isfinite(result).all():
        raise MeshProofError("nonfinite vector")
    return result


def entry(document: Document, key: str, index: object) -> Document:
    sequence = items(document.get(key))
    position = integer(index)
    if position >= len(sequence):
        raise MeshProofError(f"{key} index out of bounds")
    return obj(sequence[position])


def unsupported(document: Document, keys: tuple[str, ...]) -> None:
    if any(key in document for key in keys):
        raise MeshProofError(f"unsupported geometry fields: {keys}")
