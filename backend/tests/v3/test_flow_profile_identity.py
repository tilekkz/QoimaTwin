"""Canonical choices preserve meaning and reject private mutable state as an identity input."""

import json

from app.v3.flow_profile import compile_light_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


def test_set_order_and_reduced_rational_spelling_share_identity() -> None:
    first = document()
    second = document()
    for key in ("actors", "owners", "materials", "recipes", "orders"):
        second[key].reverse()
    first["actors"][-1]["speed_m_s"] = {"numerator": 1, "denominator": 2}
    second["actors"][0]["speed_m_s"] = {"numerator": 2, "denominator": 4}
    a = compile_light_profile(source_bundle(), source_catalog(), first)
    b = compile_light_profile(source_bundle(), source_catalog(), second)
    assert a.frozen_bytes == b.frozen_bytes and a.input_hash == b.input_hash


def test_changed_synthetic_choice_changes_identity() -> None:
    first = compile_light_profile(source_bundle(), source_catalog(), document())
    value = document()
    value["times"]["pack"] += 1
    second = compile_light_profile(source_bundle(), source_catalog(), value)
    assert first.input_hash != second.input_hash


def test_frozen_inputs_preserve_materials_sources_and_actual_initial_state() -> None:
    result = compile_light_profile(source_bundle(), source_catalog(), document())
    frozen = json.loads(result.frozen_bytes)
    assert len(frozen["source"]["documents"]) == 14
    assert frozen["conveyor"]["document"]["document_kind"] == "conveyor_topology_proposal"
    assert len(frozen["initial_state"]["stock"]["locations"]) == 12256
    assert len(frozen["initial_state"]["stock"]["containers"]) == 532
    assert len(frozen["choices"]["recipes"]) == 2
    assert len(frozen["graph"]["arcs"]) > 0
