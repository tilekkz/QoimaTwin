"""Public profile examples use explicit source inputs and independently known stock counts."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.v3.flow_profile import compile_light_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog

EXAMPLE = Path("docs/proposals/adaptive-v3/light-flow-profile.example.json")


def document() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_bytes())  # type: ignore[no-any-return]


def test_explicit_actual_source_choices_compile_to_full_stock_and_real_anchors() -> None:
    result = compile_light_profile(source_bundle(), source_catalog(), document())
    assert result.horizon_tick == 600_000_000 and result.end_tick == 1_200_000_000
    assert len(result.profile.actors) == 24
    assert len(result.profile.stock.units) == 12256
    assert len(result.profile.stock.containers) == 530
    assert result.profile.orders[0].source_node == "v3:module:SMALL_E:019:B5:worker:node"
    assert result.profile.orders[0].cart_source_node == "v3:module:SMALL_E:019:B5:cart:node"
    assert result.profile.port.service_tick == 20_000_000
    assert hashlib.sha256(result.frozen_bytes).hexdigest() == result.input_hash
    assert b"_adjacency" not in result.frozen_bytes and b'"history"' not in result.frozen_bytes


@pytest.mark.parametrize("field", ["graph", "stock", "belt_route", "intake_node", "port"])
def test_derived_fields_are_not_public_overrides(field: str) -> None:
    value = document()
    value[field] = {}
    with pytest.raises(ValueError):
        compile_light_profile(source_bundle(), source_catalog(), value)


@pytest.mark.parametrize("field", ["revision", "layout_content_hash"])
def test_wrong_source_binding_is_rejected(field: str) -> None:
    value = document()
    value["source"][field] = "wrong"
    with pytest.raises(ValueError):
        compile_light_profile(source_bundle(), source_catalog(), value)


def test_input_document_is_not_modified_by_compilation() -> None:
    value = document()
    before = copy.deepcopy(value)
    compile_light_profile(source_bundle(), source_catalog(), value)
    assert value == before
