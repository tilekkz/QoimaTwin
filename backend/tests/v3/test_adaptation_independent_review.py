"""Public planning must bind source authority and row metadata, not only numeric costs."""

from dataclasses import replace
from functools import cache
from types import MappingProxyType

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.adaptation_compare import _context, plan_horizon
from app.v3.adaptation_pin import HORIZON_PATHS, PREFIX
from app.v3.adaptation_source import AdaptationPackage, load_adaptation_package
from tests.v3.test_adaptation_source import BASE, PACKAGE


@cache
def package() -> AdaptationPackage:
    return load_adaptation_package(PACKAGE, BASE)


def test_adapted_row_module_must_match_its_verified_slot() -> None:
    source = package()
    document = source.horizon_document(1)
    document["assignments"][0]["module_id"] = "nonexistent-module"
    with pytest.raises(ValueError):
        plan_horizon(source, 1, document=document)


def test_reconstructed_package_cannot_inherit_raw_pins_after_coherent_inventory_change() -> None:
    source = package()
    baseline = source.base_document("baseline-assignment-v3.json")
    altered = source.horizon_document(1)
    hu = baseline["assignments"][0]["handling_unit_id"]
    for document in (baseline, altered):
        row = next(r for r in document["assignments"] if r["handling_unit_id"] == hu)
        row["quantity_units"] += 1
    raw, base = dict(source._raw), dict(source._base)
    raw[HORIZON_PATHS[1]] = canonical_bytes(altered)
    base[PREFIX + "baseline-assignment-v3.json"] = canonical_bytes(baseline)
    forged = replace(source, _raw=MappingProxyType(raw), _base=MappingProxyType(base))
    assert forged.entries == source.entries
    assert forged.baseline_assignment_sha256 == source.baseline_assignment_sha256
    with pytest.raises(ValueError):
        plan_horizon(forged, 1)


def test_public_context_cannot_change_verified_inventory_mass() -> None:
    source = package()
    context = _context(source)
    assert context.facts.cargo["SMALL_CARTON"]["handling_unit"]["gross_mass_kg"] == 0.94
    with pytest.raises((TypeError, ValueError)):
        context.facts.cargo["SMALL_CARTON"]["handling_unit"]["gross_mass_kg"] = 1.0
        plan_horizon(source, 1, context=context)


def test_rejected_late_route_does_not_leak_partial_projection_into_next_call() -> None:
    source = package()
    before = {name: bytes(value) for name, value in source._base.items()}
    expected = plan_horizon(source, 2)
    document = source.horizon_document(2)
    assert len(document["transfers"]) == 2
    document["transfers"][1]["loaded_route"]["arc_ids"][-1] = "missing-final-arc"
    with pytest.raises(ValueError):
        plan_horizon(source, 2, document=document)
    assert plan_horizon(source, 2) == expected
    assert {name: bytes(value) for name, value in source._base.items()} == before
    assert expected.inventory.handling_units == 530 and expected.inventory.units == 12256
    assert expected.actual_engine_run is False and expected.operational_admission is False
    assert expected.period_unit == "unclocked_planning_period"
