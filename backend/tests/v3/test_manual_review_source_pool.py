"""Source actor pools cannot be expanded by an otherwise explicit synthetic skill."""

from pathlib import Path

import pytest

from app.storage.canonical_json import parse_json
from app.v3.inputs import load_v3_bundle
from app.v3.materialize_manifest import materialized_bytes
from app.v3.profile import compile_manual_profile
from app.v3.profile_models import ManualProposal


@pytest.mark.parametrize(
    "outsider,source,skill", [("P01", "R01", "receive"), ("K01", "S01", "ship")]
)
def test_synthetic_skills_cannot_add_workers_to_fixed_source_port_pools(
    outsider: str,
    source: str,
    skill: str,
) -> None:
    data = Path(__file__).parents[2] / "data"
    proposal = ManualProposal.model_validate(
        parse_json((data / "v3-execution-proposals/manual-whole-hu-demo-v1.json").read_bytes())
    )
    home = next(a.home_node_id for a in proposal.actors if a.actor_id == source)
    changed = tuple(
        a.model_copy(update={"skills": (skill,), "home_node_id": home})
        if a.actor_id == outsider
        else a
        for a in proposal.actors
    )
    proposal = proposal.model_copy(update={"actors": changed})
    with pytest.raises(ValueError, match=r"source.*pool|pool.*source"):
        compile_manual_profile(load_v3_bundle(data / "v3-proposal"), proposal)


def test_fixed_source_pool_check_preserves_valid_materialized_bytes() -> None:
    data = Path(__file__).parents[2] / "data"
    path = data / "v3-execution-proposals/manual-whole-hu-demo-v1.json"
    proposal = ManualProposal.model_validate(parse_json(path.read_bytes()))
    compiled = compile_manual_profile(load_v3_bundle(data / "v3-proposal"), proposal)
    assert {p.direction: p.eligible_actor_ids for p in compiled.profile.ports} == {
        "inbound": frozenset({"R01", "R02"}),
        "outbound": frozenset({"S01", "S02"}),
    }
    assert materialized_bytes(compiled) == path.with_suffix(".materialized.json").read_bytes()
