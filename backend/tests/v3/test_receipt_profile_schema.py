"""Public receipt documents cannot override source facts or normalize invalid scalar types."""

from typing import Any

import pytest

from app.v3.receipt_profile_schema import validate_document
from tests.v3.test_receipt_profile_fixtures import receipt_choices


def test_explicit_receipt_profile_accepts_finite_future_definitions() -> None:
    value = receipt_choices()
    validate_document(value)
    assert value["receipts"][0]["quantity_units"] == 24


@pytest.mark.parametrize("field,bad", [("quantity_units", True), ("arrival_tick", 0.0)])
def test_receipt_quantities_and_clocks_reject_equal_noninteger_types(field: str, bad: Any) -> None:
    value = receipt_choices()
    value["receipts"][0][field] = bad
    with pytest.raises(ValueError):
        validate_document(value)


@pytest.mark.parametrize(
    "section,field",
    [
        ("receipts", "gross_mass_kg"),
        ("receipt_ports", "service_tick"),
        ("receipt_ports", "node_id"),
    ],
)
def test_public_receipt_profile_rejects_source_derived_overrides(section: str, field: str) -> None:
    value = receipt_choices()
    value[section][0][field] = 1
    with pytest.raises(ValueError):
        validate_document(value)


def test_receipt_geometry_rejects_boolean_rational_before_reduction() -> None:
    value = receipt_choices()
    value["receipt_buffers"][0]["clearance_m"]["numerator"] = True
    with pytest.raises(ValueError):
        validate_document(value)


@pytest.mark.parametrize("field", ["receipt_buffers", "receipt_ports", "receipts", "receipt_times"])
def test_receipt_profile_requires_each_process_choice(field: str) -> None:
    value = receipt_choices()
    del value[field]
    with pytest.raises(ValueError):
        validate_document(value)
