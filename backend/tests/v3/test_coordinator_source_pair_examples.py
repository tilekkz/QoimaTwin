"""Proposed mixed source pair binds both worlds; no acceptance verdict is precomputed."""

from pathlib import Path

from app.storage.canonical_json import parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_pair_inputs import prepare_coordinator_pair
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import coordinator_sources

__all__ = ["coordinator_sources"]
PROPOSALS = Path(__file__).resolve().parents[2] / "docs/proposals/adaptive-v3"


def test_mixed_source_n4_examples_differ_only_in_two_explicit_role_intents(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    baseline = parse_json((PROPOSALS / "coordinator-n4-baseline.example.json").read_bytes())
    candidate = parse_json((PROPOSALS / "coordinator-n4-candidate.example.json").read_bytes())
    assert baseline["role_intents"] == []
    assert len(candidate["role_intents"]) == 2
    assert {i["actor_id"] for i in candidate["role_intents"]} == {"P11", "P12"}
    assert {i["station_id"] for i in candidate["role_intents"]} == {"PK05", "PK06"}
    assert {k: v for k, v in candidate.items() if k != "role_intents"} == {
        k: v for k, v in baseline.items() if k != "role_intents"
    }
    prepared = prepare_coordinator_pair(*coordinator_sources, baseline, candidate, scenario="N4")
    world = prepared.baseline.profile.world
    assert len(world.receipts.flow.actors) == 24
    assert len(world.receipts.flow.stock.containers) == 530
    assert len(world.receipts.flow.stock.units) == 12_256
    assert len(world.receipts.flow.orders) == 2
    assert len(world.orders) == len(world.receipts.receipts) == 1
    assert prepared.common_input_hash == prepared.baseline.input_hash
    assert prepared.baseline.input_hash != prepared.candidate.input_hash
