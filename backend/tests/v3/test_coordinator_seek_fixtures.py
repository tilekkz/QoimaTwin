"""Hand outcomes prepared only when final tests execute; no source DES fixtures."""

from dataclasses import replace
from functools import cache
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import HandCoordinatorInputs, freeze_hand_inputs
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_coordinator_shared_world import receipt_profile_at
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


@cache
def case(kind: str) -> tuple[HandCoordinatorInputs, dict[str, Any], CoordinatorOutcome]:
    profiles: dict[str, tuple[CoordinatorProfile, int, int]] = {
        "roles": (staffing_profile(), 200, 200),
        "receipt": (receipt_profile_at(), 30, 40),
        "whole": (replace(staffing_profile(whole_order=True), intents=()), 46, 52),
        "two_carts": (multi_profile(candidate=False, two_carts=True), 110, 110),
    }
    profile, horizon_s, end_s = profiles[kind]
    source = receipt_conveyor()
    inputs = freeze_hand_inputs(profile, source, horizon_s * SECOND, end_s * SECOND)
    outcome = CoordinatorEngine(profile, source).run(inputs.horizon_tick, inputs.end_tick)
    return inputs, build_coordinator_run(inputs, outcome), outcome


def fresh_run(kind: str) -> tuple[HandCoordinatorInputs, dict[str, Any], CoordinatorOutcome]:
    from app.storage.canonical_json import canonical_bytes

    inputs, run, outcome = case(kind)
    copied = parse_json(canonical_bytes(run))
    assert isinstance(copied, dict)
    return inputs, copied, outcome
