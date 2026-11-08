"""Mutable captures reference authoritative definitions without copying immutable recipes."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_native_decode import encode
from app.v3.coordinator_run_projection import project_outcome, restore_outcome
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_receipt_flow_fixtures import SECOND


def test_compact_capture_keeps_native_state_but_excludes_immutable_recipes() -> None:
    profile, outcome = role_case(105 * SECOND)
    compact = project_outcome(profile, outcome)
    raw = canonical_bytes(compact)
    assert b'"recipe"' not in raw
    assert b'"origin_hu"' not in raw
    assert b'"quantity_units"' not in raw
    assert encode(restore_outcome(profile, compact)) == encode(outcome)
    assert compact["at_end"]["inventory"]["claim_generation"] == 0
    assert len(compact["at_end"]["carts"]) == 1


def test_unknown_container_reference_cannot_create_material_from_capture() -> None:
    profile, outcome = role_case(105 * SECOND)
    compact = deepcopy(project_outcome(profile, outcome))
    compact["at_end"]["stock"]["containers"][0]["container_id"] = "UNDECLARED"
    with pytest.raises(ValueError, match="container"):
        restore_outcome(profile, compact)


def test_injected_recipe_cannot_override_the_input_authority() -> None:
    profile, outcome = role_case(105 * SECOND)
    compact = deepcopy(project_outcome(profile, outcome))
    compact["at_end"]["stock"]["containers"][0]["recipe"] = {}
    with pytest.raises(ValueError, match="fields"):
        restore_outcome(profile, compact)
