"""Independent profile expectations for the new frontend helper-identity proposal."""

from pathlib import Path

from app.storage.canonical_json import parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_pair_inputs import prepare_coordinator_pair
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import coordinator_sources

__all__ = ["coordinator_sources"]
PROPOSALS = Path(__file__).resolve().parents[2] / "docs/proposals/adaptive-v3"


def test_frontend_helper_proposal_preserves_full_common_choices_and_source_population(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    baseline = parse_json((PROPOSALS / "coordinator-tilek-n4-baseline.example.json").read_bytes())
    candidate = parse_json((PROPOSALS / "coordinator-tilek-n4-candidate.example.json").read_bytes())
    assert baseline["role_intents"] == []
    assert {i["actor_id"] for i in candidate["role_intents"]} == {"P01", "P02"}
    assert {i["station_id"] for i in candidate["role_intents"]} == {"PK05", "PK06"}
    assert {k: v for k, v in baseline.items() if k != "role_intents"} == {
        k: v for k, v in candidate.items() if k != "role_intents"
    }
    helpers = {
        row["actor_id"]
        for row in baseline["registry"]["workers"]
        if row["primary_role"] == "pick" and "pack" in row["eligible_roles"]
    }
    assert helpers == {"P01", "P02"}
    for actor in baseline["actors"]:
        if actor["actor_id"] in helpers:
            assert actor["speed_m_s"] == {"numerator": 6, "denominator": 5}
    prepared = prepare_coordinator_pair(*coordinator_sources, baseline, candidate, scenario="N4")
    world = prepared.baseline.profile.world
    assert len(world.receipts.flow.actors) == 24
    assert len(world.receipts.flow.stock.containers) == 530
    assert len(world.receipts.flow.stock.units) == 12_256
    assert prepared.common_input_hash == prepared.baseline.input_hash
    assert prepared.baseline.input_hash != prepared.candidate.input_hash
