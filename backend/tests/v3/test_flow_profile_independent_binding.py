"""Equal Python values and equal wire projections cannot replace verified typed source."""

from dataclasses import replace
from fractions import Fraction as F
from types import MappingProxyType
from typing import cast

import pytest

from app.v3.flow_profile import compile_light_profile
from app.v3.flow_profile_sources import verified_records
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


def test_fraction_shaped_mapping_cannot_impersonate_verified_conveyor_speed() -> None:
    source = source_catalog()
    disguised = {
        "numerator": source.speed_m_s.numerator,
        "denominator": source.speed_m_s.denominator,
    }
    changed = replace(source, speed_m_s=cast(F, disguised))
    request = document()
    request["orders"] = []  # Authority must not depend on whether a speed is exercised today.
    with pytest.raises(ValueError, match=r"pinned|typed|source"):
        compile_light_profile(source_bundle(), changed, request)


def test_boolean_cell_capacity_cannot_use_integer_one_equality() -> None:
    source = source_catalog()
    cells = dict(source.cells)
    identity = next(iter(cells))
    assert type(cells[identity].capacity) is int and cells[identity].capacity == 1
    cells[identity] = replace(cells[identity], capacity=True)
    changed = replace(source, cells=MappingProxyType(cells))
    with pytest.raises(ValueError, match="pinned"):
        verified_records(source_bundle(), changed)


def test_fraction_quantity_cannot_replace_equal_integer_source_units() -> None:
    bundle = source_bundle()
    original = bundle.handling_units[0]
    changed = replace(original, quantity_units=cast(int, F(original.quantity_units)))
    altered = replace(bundle, handling_units=(changed, *bundle.handling_units[1:]))
    with pytest.raises(ValueError, match="pinned"):
        verified_records(altered, source_catalog())


def test_integer_zero_cannot_replace_source_boolean_permission() -> None:
    bundle = source_bundle()
    index = next(i for i, slot in enumerate(bundle.slots) if slot.retrieval_blocked is False)
    slots = list(bundle.slots)
    slots[index] = replace(slots[index], retrieval_blocked=cast(bool, 0))
    with pytest.raises(ValueError, match="pinned"):
        verified_records(replace(bundle, slots=tuple(slots)), source_catalog())
