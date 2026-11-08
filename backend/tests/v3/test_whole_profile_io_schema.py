"""The public whole profile permits choices, never source-derived overrides."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.v3.whole_profile_schema import validate_document, whole_profile_schema


def document() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "docs/proposals/adaptive-v3/whole-flow-profile.example.json"
    result: dict[str, Any] = json.loads(path.read_bytes())
    return result


def test_explicit_example_and_published_schema_agree() -> None:
    validate_document(document())
    assert whole_profile_schema()["additionalProperties"] is False


@pytest.mark.parametrize("field", ["graph", "stock", "port_service_tick", "source_hashes"])
def test_source_derived_overrides_reject(field: str) -> None:
    value = document()
    value[field] = {}
    with pytest.raises(ValueError):
        validate_document(value)


@pytest.mark.parametrize("invalid", [True, 1.5, {"numerator": 1, "denominator": 0}])
def test_exact_clock_and_rational_grammar(invalid: Any) -> None:
    value = document()
    value["actors"][0]["speed_m_s"] = invalid
    with pytest.raises(ValueError):
        validate_document(value)


def test_source_pin_and_port_service_are_not_public_choices() -> None:
    value = document()
    value["source"]["revision"] = "stale"
    with pytest.raises(ValueError):
        validate_document(value)
    value = document()
    value["whole_ports"][0]["service_ticks"] = [["STANDARD_CARTON", 1]]
    with pytest.raises(ValueError):
        validate_document(value)
