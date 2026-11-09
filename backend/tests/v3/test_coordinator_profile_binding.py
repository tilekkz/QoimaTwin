"""Adjacent authority tests are written first, with no deferred-check claim of GREEN."""

import json
from dataclasses import replace
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_profile import (
    compile_coordinator_profile,
    load_coordinator_inputs,
    validate_compiled_coordinator,
)
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import coordinator_document, coordinator_sources

__all__ = ["coordinator_sources"]


def test_retained_actor_boolean_alias_cannot_inherit_frozen_identity(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    compiled = compile_coordinator_profile(*coordinator_sources, coordinator_document())
    actor = compiled.profile.world.receipts.flow.actors[0]
    object.__setattr__(actor, "available_tick", False)
    with pytest.raises(ValueError):
        validate_compiled_coordinator(compiled, coordinator_sources[1])


@pytest.mark.parametrize("field", ["engine_version", "registry_common_hash", "graph"])
def test_frozen_reader_reconstructs_authority_instead_of_trusting_projection(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    field: str,
) -> None:
    compiled = compile_coordinator_profile(*coordinator_sources, coordinator_document())
    value = json.loads(compiled.frozen_bytes)
    value[field] = "forged"
    with pytest.raises(ValueError):
        load_coordinator_inputs(canonical_bytes(value))


def test_explicit_choice_cannot_reuse_other_frozen_profile(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    compiled = compile_coordinator_profile(*coordinator_sources, coordinator_document())
    forged = replace(compiled, horizon_tick=compiled.horizon_tick - 1)
    with pytest.raises(ValueError):
        validate_compiled_coordinator(forged, coordinator_sources[1])


@pytest.mark.parametrize("table", ["goods_stations", "picker_bindings", "unit_assignments"])
def test_missing_resources_do_not_create_implicit_default_resources(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    table: str,
) -> None:
    value = coordinator_document()
    value[table].pop()
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, value)


def test_compile_does_not_construct_or_run_an_engine(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Compiler must remain pure admission")

    monkeypatch.setattr("app.v3.coordinator_engine.CoordinatorEngine.__init__", forbidden)
    compiled = compile_coordinator_profile(*coordinator_sources, coordinator_document())
    assert compiled.input_hash
