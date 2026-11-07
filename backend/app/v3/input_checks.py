"""Small path-aware checks shared by static input validators."""

import math
from fractions import Fraction
from typing import Any

from jsonschema import Draft202012Validator

from .input_json import PREFIX
from .input_models import V3InputError

# Only serialized derived arithmetic; never admissibility, ledgers, counts or identities.
ARITHMETIC_ABS_TOLERANCE = 1e-8


def require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise V3InputError(f"{path}: {reason}")


def close(actual: float, expected: float, path: str) -> None:
    require(
        math.isclose(actual, expected, rel_tol=0, abs_tol=ARITHMETIC_ABS_TOLERANCE),
        path,
        f"arithmetic mismatch: {actual} != {expected}",
    )


def exact(value: Any) -> Fraction:
    """Interpret source numbers as decimal values, independent of Decimal context."""
    return Fraction(str(value))


def positive(value: Any, path: str, *, integer: bool = False) -> None:
    kind = int if integer else (int, float)
    require(
        not isinstance(value, bool) and isinstance(value, kind),
        path,
        "expected positive integer" if integer else "expected positive finite number",
    )
    require(math.isfinite(value) and value > 0, path, "expected positive finite number")


def rows(document: Any, key: str, path: str) -> list[dict[str, Any]]:
    require(isinstance(document, dict), path, "expected object")
    value = document.get(key)
    require(isinstance(value, list), f"{path}/{key}", "expected array")
    result: list[dict[str, Any]] = value
    for i, row in enumerate(result):
        require(isinstance(row, dict), f"{path}/{key}/{i}", "expected object")
    return result


def indexed(records: list[dict[str, Any]], key: str, path: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for i, row in enumerate(records):
        value = row.get(key, "")
        location = f"{path}/{i}/{key}"
        require(isinstance(value, str) and bool(value), location, "expected nonempty identity")
        require(value not in result, location, f"duplicate identity {value}")
        result[value] = row
    return result


def schema_check(value: Any, schema: Any, path: str) -> None:
    Draft202012Validator.check_schema(schema)
    # Schemas ship only local JSON pointers. No remote resolution is allowed.
    reject_remote_refs(schema, path)
    error = next(Draft202012Validator(schema).iter_errors(value), None)
    if error is not None:
        pointer = "/".join(str(part) for part in error.absolute_path)
        raise V3InputError(f"{path}/{pointer}: schema violation: {error.message}")


def reject_remote_refs(value: Any, path: str) -> None:
    if isinstance(value, dict):
        if "$ref" in value:
            require(value["$ref"].startswith("#"), path, "external schema reference forbidden")
        for child in value.values():
            reject_remote_refs(child, path)
    elif isinstance(value, list):
        for child in value:
            reject_remote_refs(child, path)


def get_document(documents: dict[str, Any], name: str) -> Any:
    path = PREFIX + name
    require(path in documents, path, "required document missing")
    return documents[path]
