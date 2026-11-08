"""Role choices stay explicit and cannot alter the frozen physical world silently."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import coordinator_document, coordinator_sources

__all__ = ["coordinator_sources"]


def test_idle_p01_needs_no_implicit_cart_eligibility_for_internal_alias(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    value = coordinator_document()
    value["unit_assignments"][0]["picker_id"] = "P03"
    next(row for row in value["picker_bindings"] if row["actor_id"] == "P01")["cart_ids"] = []
    compiled = compile_coordinator_profile(*coordinator_sources, value)
    assert compiled.profile.world.receipts.flow.picker_id == "P01"
    resources = compiled.profile.unit_resources
    assert resources is not None
    assert all(a.picker_id != "P01" for a in resources.assignments)


def test_role_intent_uses_actual_source_route_and_explicit_common_break(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    value = coordinator_document()
    value["registry"]["unavailability"] = [
        {
            "actor_id": "K05",
            "start_tick": 100_000_000,
            "end_tick": 800_000_000,
            "reason": "explicit source example window, not a source work norm",
        }
    ]
    value["role_intents"] = [
        {
            "intent_id": "HELP-P11-PK05",
            "actor_id": "P11",
            "station_id": "PK05",
            "request_tick": 100_000_000,
            "return_tick": 700_000_000,
            "restore_by_tick": 800_000_000,
        }
    ]
    compiled = compile_coordinator_profile(*coordinator_sources, value)
    actor = next(a for a in compiled.profile.world.receipts.flow.actors if a.actor_id == "P11")
    assert compiled.profile.intents[0].restore_node == actor.home
    frozen = parse_json(compiled.frozen_bytes)
    assert frozen["choices"]["role_intents"] == value["role_intents"]
    baseline = deepcopy(value)
    baseline["role_intents"] = []
    plain = compile_coordinator_profile(*coordinator_sources, baseline)
    assert plain.registry_common_hash == compiled.registry_common_hash
    assert plain.input_hash != compiled.input_hash


def test_unknown_role_worker_or_uncovered_break_is_rejected(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    value = coordinator_document()
    value["role_intents"] = [
        {
            "intent_id": "HELP",
            "actor_id": "P11",
            "station_id": "PK05",
            "request_tick": 200_000_000,
            "return_tick": 210_000_000,
            "restore_by_tick": 220_000_000,
        }
    ]
    with pytest.raises(ValueError, match="COMMON_PRIMARY_BREAK"):
        compile_coordinator_profile(*coordinator_sources, value)
