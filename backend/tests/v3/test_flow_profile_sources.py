"""A retained raw digest cannot certify altered typed source fields."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.flow_profile import compile_light_profile
from app.v3.flow_profile_sources import verified_records
from app.v3.input_models import ImmutableDocument
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


def test_changed_conveyor_speed_with_old_raw_hash_is_rejected() -> None:
    changed = replace(source_catalog(), speed_m_s=F(99))
    with pytest.raises(ValueError, match="pinned"):
        compile_light_profile(source_bundle(), changed, document())


def test_changed_typed_port_clock_with_unchanged_document_is_rejected() -> None:
    bundle = source_bundle()
    port = next(p for p in bundle.ports if p.port_id == "OUT_S_EXPRESS")
    changed_port = replace(port, seconds_by_archetype=(("SMALL_CARTON", 1.0),))
    changed = replace(bundle, ports=tuple(changed_port if p is port else p for p in bundle.ports))
    with pytest.raises(ValueError, match="pinned"):
        compile_light_profile(changed, source_catalog(), document())


def test_changed_canonical_document_bytes_cannot_reuse_original_digest() -> None:
    source = source_catalog()
    changed = replace(source, document=ImmutableDocument(source.document.canonical_bytes + b" "))
    with pytest.raises(ValueError, match="pinned"):
        verified_records(source_bundle(), changed)
