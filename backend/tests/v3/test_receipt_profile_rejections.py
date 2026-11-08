"""Declared receipts cannot create stock by overriding geometry or source identities."""

from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest

from app.v3.receipt_profile import compile_receipt_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_receipt_profile_fixtures import receipt_choices


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot_id", "v3:slot:SMALL_E:019:L1:B5"),
        ("sku_id", "missing"),
        ("quantity_units", 23),
        ("port_id", "OUT_S_EXPRESS"),
        ("arrival_tick", 1_200_000_000),
    ],
)
def test_receipt_rejects_foreign_or_unavailable_source_choice(field: str, value: Any) -> None:
    document = receipt_choices()
    document["receipts"][0][field] = value
    with pytest.raises(ValueError):
        compile_receipt_profile(source_bundle(), source_catalog(), document)


@pytest.mark.parametrize("section", ["receipts", "receipt_ports", "receipt_buffers"])
def test_duplicate_receipt_table_identity_is_rejected(section: str) -> None:
    document = receipt_choices()
    document[section].append(document[section][0].copy())
    with pytest.raises(ValueError):
        compile_receipt_profile(source_bundle(), source_catalog(), document)


def test_caller_cannot_substitute_typed_source_with_same_raw_digest() -> None:
    source = source_catalog()
    changed = replace(source, speed_m_s=Fraction(99))
    with pytest.raises(ValueError, match="pinned"):
        compile_receipt_profile(source_bundle(), changed, receipt_choices())


def test_wrong_declared_source_revision_is_rejected() -> None:
    document = receipt_choices()
    document["source"]["revision"] = "wrong"
    with pytest.raises(ValueError):
        compile_receipt_profile(source_bundle(), source_catalog(), document)


def test_buffer_connector_must_start_at_actual_port_service() -> None:
    document = receipt_choices()
    document["receipt_buffers"][0]["path_xz"][0][0]["numerator"] = 1
    with pytest.raises(ValueError):
        compile_receipt_profile(source_bundle(), source_catalog(), document)


def test_cross_port_buffer_binding_is_rejected() -> None:
    document = receipt_choices()
    document["receipt_buffers"][0]["port_id"] = "IN_N_STANDARD"
    with pytest.raises(ValueError):
        compile_receipt_profile(source_bundle(), source_catalog(), document)
