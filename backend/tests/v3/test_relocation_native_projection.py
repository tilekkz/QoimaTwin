"""Compact N1 records retain extension state and use immutable input recipes."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_native_decode import encode
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_native_projection import project_outcome, restore_outcome
from app.v3.relocation_observe import RelocationEvent, RelocationOutcome
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def test_compact_partial_preserves_custody_claims_and_relocation_progress() -> None:
    profile = relocation_hand()
    outcome = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 6 * SECOND)
    assert type(outcome) is RelocationOutcome
    compact = project_outcome(profile.coordinator, outcome)
    raw = canonical_bytes(compact)
    assert b'"recipe"' not in raw and b'"origin_hu"' not in raw
    assert compact["at_end"]["relocations"][0]["taken_tick"] == 4 * SECOND
    assert compact["at_end"]["relocations"][0]["placed_tick"] is None
    restored = restore_outcome(profile.coordinator, compact)
    assert type(restored) is RelocationOutcome
    assert any(type(event) is RelocationEvent for event in restored.events)
    assert encode(restored) == encode(outcome)


@pytest.mark.parametrize("change", ["unknown_unit", "recipe", "missing_progress"])
def test_compact_extension_cannot_forge_immutable_definitions_or_drop_progress(change: str) -> None:
    profile = relocation_hand()
    outcome = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 6 * SECOND)
    assert type(outcome) is RelocationOutcome
    compact = deepcopy(project_outcome(profile.coordinator, outcome))
    state = compact["at_end"]
    if change == "unknown_unit":
        delta = next(event["delta"] for event in compact["events"] if event["delta"] is not None)
        delta["before"][0]["units"][0]["token"]["unit_id"] = "NEW_UNDECLARED_UNIT"
    elif change == "recipe":
        state["stock"]["containers"][0]["recipe"] = {}
    else:
        del state["relocations"]
    with pytest.raises(ValueError):
        restore_outcome(profile.coordinator, compact)


def test_plain_coordinator_outcome_is_not_implicitly_promoted_to_n1() -> None:
    profile = replace(relocation_hand(), jobs=())
    outcome = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 2 * SECOND)
    with pytest.raises(ValueError, match="Exact relocation"):
        project_outcome(profile.coordinator, outcome)
