"""Prewritten input gates; source compilation is distinct from running either world."""

from copy import deepcopy

import pytest

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_pair_inputs import prepare_coordinator_pair
from app.v3.coordinator_pair_models import IncomparableCoordinatorPair, UnsupportedPairScenario
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import (
    coordinator_document,
    coordinator_sources,
)

__all__ = ["coordinator_sources"]


@pytest.mark.parametrize("scenario", ["N1", "N2", "N3", "N5", True, 0, None])
def test_unsupported_scenario_is_rejected_before_source_or_engine(scenario: object) -> None:
    with pytest.raises(UnsupportedPairScenario):
        prepare_coordinator_pair(None, None, {}, {}, scenario=scenario)  # type: ignore[arg-type]


def test_noop_uses_exact_full_frozen_common_input(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    bundle, conveyor = coordinator_sources
    document = coordinator_document()
    clone = deepcopy(document)
    for key in ("actors", "owners", "orders", "goods_stations", "carts", "picker_bindings"):
        clone[key].reverse()
    prepared = prepare_coordinator_pair(bundle, conveyor, document, clone, scenario="N0")
    assert prepared.baseline is not prepared.candidate
    assert prepared.baseline.frozen_bytes == prepared.candidate.frozen_bytes
    assert prepared.common_input_hash == prepared.baseline.input_hash
    assert prepared.common_input_hash != prepared.baseline.registry_common_hash
    assert document == coordinator_document()


@pytest.mark.parametrize("field", ["profile_id", "provenance", "horizon_tick"])
def test_metadata_and_clock_drift_are_not_excluded_from_common_input(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    field: str,
) -> None:
    bundle, conveyor = coordinator_sources
    baseline = coordinator_document()
    candidate = deepcopy(baseline)
    candidate[field] = (
        candidate[field] + 1 if field == "horizon_tick" else candidate[field] + "-new"
    )
    with pytest.raises(IncomparableCoordinatorPair, match="PHYSICAL_COMMON_INPUT_DRIFT"):
        prepare_coordinator_pair(bundle, conveyor, baseline, candidate, scenario="N0")


def test_invalid_candidate_does_not_become_a_neutral_hash(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    bundle, conveyor = coordinator_sources
    baseline = coordinator_document()
    candidate = deepcopy(baseline)
    candidate["horizon_tick"] = True
    with pytest.raises(ValueError):
        prepare_coordinator_pair(bundle, conveyor, baseline, candidate, scenario="N4")


def test_source_n4_changes_only_the_explicit_role_plan(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    baseline = coordinator_document()
    baseline["horizon_tick"] = 1_700_000_000
    baseline["registry"]["unavailability"] = [
        {
            "actor_id": actor,
            "start_tick": 100_000_000,
            "end_tick": 1_600_000_000,
            "reason": "explicit paired example assumption",
        }
        for actor in ("K05", "K06")
    ]
    candidate = deepcopy(baseline)
    candidate["role_intents"] = [
        {
            "intent_id": f"HELP-{actor}",
            "actor_id": actor,
            "station_id": station,
            "request_tick": 100_000_000,
            "return_tick": 1_200_000_000,
            "restore_by_tick": 1_600_000_000,
        }
        for actor, station in (("P11", "PK05"), ("P12", "PK06"))
    ]
    prepared = prepare_coordinator_pair(*coordinator_sources, baseline, candidate, scenario="N4")
    assert prepared.baseline.input_hash != prepared.candidate.input_hash
    assert prepared.baseline.registry_common_hash == prepared.candidate.registry_common_hash
    assert prepared.common_input_hash == prepared.baseline.input_hash
    assert len(prepared.candidate.profile.world.receipts.flow.actors) == 24
