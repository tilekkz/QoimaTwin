"""Rehashing malformed claims cannot make them a possible manual engine run."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run, run_identity, validate_manual_run
from tests.v3.test_run_fixtures import manual_profile


@pytest.mark.parametrize("damage", ["class", "mass", "dimensions", "direction", "skill", "window"])
def test_rehashed_manual_run_keeps_capability_and_assignment_constraints(damage: str) -> None:
    profile, graph, document = manual_profile("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(32_000_000, 40_000_000)
    value = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    value = deepcopy(value)
    hu = value["profile"]["handling_units"][0]
    if damage == "class":
        hu["archetype"] = "IBC"
    elif damage == "mass":
        hu["gross_mass_kg"] = {"numerator": 654, "denominator": 1}
    elif damage == "dimensions":
        hu["dimensions_xyz_m"][0] = {"numerator": 100, "denominator": 1}
    elif damage == "direction":
        value["profile"]["ports"][0]["direction"] = "inbound"
    elif damage == "window":
        value["profile"]["ports"][0]["windows"] = [[0, 1_000_000]]
    else:
        next(a for a in value["profile"]["actors"] if a["actor_id"] == "R01")["skills"] = []
    value["run_id"] = run_identity(value)
    with pytest.raises(ValueError):
        validate_manual_run(value)


@pytest.mark.parametrize("damage", ["imaginary_buffer", "unleased_carrier"])
def test_self_consistent_trace_cannot_create_capacity_or_teleport_cargo(damage: str) -> None:
    profile, graph, document = manual_profile("outbound")
    outcome = ManualEngine(profile, graph, check_invariants=True).run(32_000_000, 40_000_000)
    changed = []
    for event in outcome.events:
        if damage == "imaginary_buffer" and event.resource_ids == ("buffer:BUFFER",):
            event = replace(event, resource_ids=("buffer:imaginary",))
        if (
            damage == "unleased_carrier"
            and event.owner is not None
            and event.owner.kind == "worker"
        ):
            event = replace(event, owner=replace(event.owner, location_id="K01"))
        changed.append(event)
    outcome = replace(outcome, events=tuple(changed))
    with pytest.raises(ValueError):
        build_manual_run(
            profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
        )
