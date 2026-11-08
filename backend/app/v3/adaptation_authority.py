"""Public planning rejects reconstructed packages or contexts with stale source authority."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from functools import cache
from pathlib import Path
from typing import Any

from app.v3.adaptation_source import AdaptationPackage, load_adaptation_package


def _same_types(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if is_dataclass(expected) and not isinstance(expected, type):
        return all(
            _same_types(getattr(actual, field.name), getattr(expected, field.name))
            for field in fields(expected)
        )
    if isinstance(expected, Mapping):
        return actual.keys() == expected.keys() and all(
            _same_types(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(
            _same_types(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return True


def require_same_authority(actual: Any, expected: Any) -> None:
    if not _same_types(actual, expected) or actual != expected:
        raise ValueError("Planning facts differ from verified pinned source authority")


@cache
def _reference() -> AdaptationPackage:
    data = Path(__file__).resolve().parents[2] / "data"
    return load_adaptation_package(data / "v3-adaptation-proposal", data / "v3-proposal")


def verify_package(package: AdaptationPackage) -> None:
    require_same_authority(package, _reference())
