"""Exact runtime types for the bounded staffing proposal; no numeric coercion."""

from typing import Any, Literal, cast

Role = Literal["pick", "pack", "receive", "ship", "forklift"]
ROLES: tuple[Role, ...] = ("pick", "pack", "receive", "ship", "forklift")
EQUIPMENT = frozenset({"manual_cart", "FL01", "FL02"})
REGISTRY_VERSION = "qoima-staff-registry-0.1.0"


def text(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("STAFF_TEXT_REQUIRED")
    return value


def tick(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("STAFF_NONNEGATIVE_INTEGER_TICK_REQUIRED")
    return value


def period(start: object, end: object) -> None:
    if tick(start) >= tick(end):
        raise ValueError("STAFF_POSITIVE_PERIOD_REQUIRED")


def role(value: object) -> Role:
    if text(value) not in ROLES:
        raise ValueError("UNKNOWN_STAFF_ROLE")
    return cast(Role, value)


def object_fields(value: object, names: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(k) is not str for k in value):
        raise ValueError("STAFF_OBJECT_REQUIRED")
    if set(value) != set(names.split()):
        raise ValueError("STAFF_FIELDS_DIFFER")
    return cast(dict[str, Any], value)


def array(value: object) -> list[Any]:
    if type(value) is not list:
        raise ValueError("STAFF_ARRAY_REQUIRED")
    return value


def string_set(value: object) -> tuple[str, ...]:
    result = tuple(text(item) for item in array(value))
    if len(set(result)) != len(result):
        raise ValueError("DUPLICATE_STAFF_SET_VALUE")
    return tuple(sorted(result))


def typed_tuple(value: object, cls: type[object]) -> None:
    if type(value) is not tuple or any(type(item) is not cls for item in value):
        raise ValueError("STAFF_EXACT_TYPED_TUPLE_REQUIRED")
