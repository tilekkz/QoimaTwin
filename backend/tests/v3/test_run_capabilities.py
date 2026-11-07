"""Rehashed input mutation cannot authorize unsupported actual work."""

import pytest

from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run, run_identity, validate_manual_run
from tests.v3.test_run_fixtures import manual_profile


@pytest.mark.parametrize("damage", ["IBC", "mass", "dimension", "port", "skill", "eligible"])
def test_executed_work_requires_profile_and_actual_actor_capability(damage: str) -> None:
    profile, graph, document = manual_profile("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(32_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    unit = run["profile"]["handling_units"][0]
    if damage == "IBC":
        unit["archetype"] = "IBC"
    elif damage == "mass":
        unit["gross_mass_kg"] = {"numerator": 654, "denominator": 1}
    elif damage == "dimension":
        unit["dimensions_xyz_m"][0] = {"numerator": 100, "denominator": 1}
    elif damage == "port":
        run["profile"]["ports"][0]["direction"] = "inbound"
    elif damage == "skill":
        next(a for a in run["profile"]["actors"] if a["actor_id"] == "R01")["skills"] = []
    else:
        run["profile"]["ports"][0]["eligible_actor_ids"] = ["R02"]
    run["run_id"] = run_identity(run)
    with pytest.raises(ValueError):
        validate_manual_run(run)
