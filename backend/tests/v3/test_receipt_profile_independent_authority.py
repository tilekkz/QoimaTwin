"""A receipt compiler cannot inherit stale source authority or precredit malformed offers."""

from dataclasses import replace
from typing import Any

import pytest

from app.v3.receipt_profile import compile_receipt_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_receipt_profile_fixtures import receipt_choices


def test_source_port_service_cannot_change_under_original_documents_and_hashes() -> None:
    bundle = source_bundle()
    ports = tuple(
        replace(p, seconds_by_archetype=tuple((cargo, 99.0) for cargo, _ in p.seconds_by_archetype))
        if p.port_id == "IN_E_PARCEL"
        else p
        for p in bundle.ports
    )
    altered = replace(bundle, ports=ports)
    assert altered.source_inventory == bundle.source_inventory
    assert altered.documents is bundle.documents
    with pytest.raises(ValueError, match="pinned"):
        compile_receipt_profile(altered, source_catalog(), receipt_choices())


@pytest.mark.parametrize(
    "field,value",
    [
        ("hu_id", "v3:HU:initial:DEMO_001:01"),
        ("slot_id", "v3:slot:STANDARD_W:001:L2:B1"),
        ("quantity_units", 48),
    ],
)
def test_invalid_future_offer_cannot_reuse_baseline_or_reserve_storage(
    field: str, value: Any
) -> None:
    bundle = source_bundle()
    original_units = bundle.handling_units
    if field == "slot_id":
        assert any(s.slot_id == value and s.reserve_only for s in bundle.slots)
    if field == "hu_id":
        assert any(hu.handling_unit_id == value for hu in original_units)
    original_documents = {k: v.canonical_bytes for k, v in bundle.documents.items()}
    document = receipt_choices()
    document["receipts"][0][field] = value
    with pytest.raises(ValueError):
        compile_receipt_profile(bundle, source_catalog(), document)
    assert bundle.handling_units is original_units
    assert bundle.baseline.quantity_units == 12256
    assert original_documents == {k: v.canonical_bytes for k, v in bundle.documents.items()}
