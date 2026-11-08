"""Finite handoff owners and exact clocks must be valid before any paid action."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.light_flow_engine import LightFlowEngine
from app.v3.runtime_graph import DirectedGraph
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


@pytest.mark.parametrize(
    "corruption",
    [
        "port_time",
        "window",
        "home",
        "empty_owner",
        "belt_owner",
        "cart_owner",
        "short_belt",
        "short_output",
    ],
)
def test_bad_clock_or_unbound_physical_owner_is_rejected_at_construction(corruption: str) -> None:
    profile = hand_profile()
    if corruption == "port_time":
        profile = replace(profile, port=replace(profile.port, service_tick=0))
    elif corruption == "window":
        profile = replace(profile, port=replace(profile.port, windows=((-1, 20_000_000),)))
    elif corruption == "home":
        profile = replace(
            profile,
            actors=tuple(
                replace(a, home="KH") if a.actor_id == "P01" else a for a in profile.actors
            ),
        )
    elif corruption == "empty_owner":
        profile = replace(profile, station=replace(profile.station, empty_owner="unknown"))
    elif corruption == "belt_owner":
        profile = replace(
            profile, owners=tuple(o for o in profile.owners if o.owner_id != "belt:O1")
        )
    elif corruption == "short_belt":
        profile = replace(profile, belt_route=profile.belt_route[2:])
    elif corruption == "short_output":
        profile = replace(profile, belt_route=profile.belt_route[:-1])
    else:
        profile = replace(profile, cart=replace(profile.cart, owner_id="unknown"))
    with pytest.raises(ValueError):
        LightFlowEngine(profile, source_catalog())


def test_carried_material_outer_width_must_fit_explicit_pedestrian_connector() -> None:
    profile = hand_profile()
    arcs = tuple(
        replace(a, clear_width_m=F(".2")) if a.source == "PARK" and a.target == "IN" else a
        for a in profile.graph.arcs
    )
    graph = DirectedGraph("too-narrow", profile.graph.node_ids, arcs)
    with pytest.raises(ValueError, match="route"):
        LightFlowEngine(replace(profile, graph=graph), source_catalog())
