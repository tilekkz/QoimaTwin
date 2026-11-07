"""Boundary and accounting failures outside the single-job analytical timeline."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_invariants import check_manual_invariants
from app.v3.execution_types import HUOwner, InitialPlacement, Lease
from tests.v3.test_execution_manual import fixture, tick


def test_future_window_wakes_before_open_to_pay_empty_approach() -> None:
    profile, graph = fixture()
    port = replace(profile.ports[0], windows=((tick(5), tick(15)),))
    result = ManualEngine(replace(profile, ports=(port,)), graph, check_invariants=True).run(
        tick(30), tick(40)
    )
    starts = [
        e.tick
        for e in result.events
        if e.kind == "operation_started" and e.stage == "intake_service"
    ]
    assert starts == [tick(5)]
    assert result.at_end.status == "complete"
    assert result.at_end.tick == tick(36)


def test_inert_heavy_initial_inventory_is_conserved_without_manual_capability() -> None:
    profile, graph = fixture()
    heavy = replace(
        profile.handling_units[0],
        hu_id="heavy",
        sku_id="HEAVY",
        archetype="IBC",
        gross_mass_kg=F(654),
        quantity=1,
    )
    slot = replace(
        profile.slots[0],
        place_id="heavy-slot",
        node_id="vehicle-only-anchor",
        max_payload_kg=F(1000),
        allowed_archetypes=frozenset({"IBC"}),
    )
    profile = replace(
        profile,
        slots=(*profile.slots, slot),
        handling_units=(*profile.handling_units, heavy),
        initial_placements=(InitialPlacement("heavy", "heavy-slot"),),
    )
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(40), tick(40))
    assert result.at_end.stock_units == (("HEAVY", 1), ("SKU1", 24))
    assert all(e.hu_id != "heavy" for e in result.events)


def test_owner_of_unknown_stock_place_is_detected() -> None:
    profile, graph = fixture("outbound")
    engine = ManualEngine(profile, graph, check_invariants=True)
    engine.state.owners["HU1"] = HUOwner("HU1", "stock", "imaginary-slot")
    with pytest.raises(RuntimeError, match="invariant"):
        check_manual_invariants(engine.state)


def test_forged_capacity_resource_is_detected() -> None:
    profile, graph = fixture()
    engine = ManualEngine(profile, graph, check_invariants=True)
    engine.state.leases["buffer:imaginary"] = Lease("buffer:imaginary", "job1", 0)
    with pytest.raises(RuntimeError, match="invariant"):
        check_manual_invariants(engine.state)


@pytest.mark.parametrize("horizon,end", [(True, 40), (0, 40), (40, 20)])
def test_invalid_boundaries_fail(horizon: int, end: int) -> None:
    profile, graph = fixture()
    with pytest.raises(ValueError, match="boundaries"):
        ManualEngine(profile, graph, check_invariants=True).run(horizon, end)


def test_arrival_at_horizon_is_rejected_instead_of_counted() -> None:
    profile, graph = fixture()
    profile = replace(profile, jobs=(replace(profile.jobs[0], arrival_tick=tick(10)),))
    with pytest.raises(ValueError, match="arrivals"):
        ManualEngine(profile, graph, check_invariants=True).run(tick(10), tick(40))


def test_engine_is_one_shot() -> None:
    profile, graph = fixture()
    engine = ManualEngine(profile, graph, check_invariants=True)
    engine.run(tick(40), tick(40))
    with pytest.raises(ValueError, match="one-shot"):
        engine.run(tick(40), tick(40))
