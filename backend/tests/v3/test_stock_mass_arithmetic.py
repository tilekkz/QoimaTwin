"""Exact arithmetic, strict recipe types and call-local identity authority."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.stock_mass import _MassPass, _MassTotals
from app.v3.stock_models import StockError, UnitRecipe


def recipe(net: str = "1", tare: str = ".1", width: str = ".5") -> UnitRecipe:
    return UnitRecipe("SMALL_CARTON", (F(width), F(1), F(1)), F(net), F(tare))


def total(*values: UnitRecipe) -> _MassTotals:
    scope = _MassPass()
    for value in values:
        scope.add(value, "all")
    return scope.totals("all")


def test_same_archetype_keeps_distinct_mass_and_empty_bucket_exact() -> None:
    assert total(recipe(), recipe(), recipe("2", ".2")) == _MassTotals(F(4), F(".4"), F("4.4"))
    assert total() == _MassTotals(F(0), F(0), F(0))


def test_equal_gross_keeps_net_tare_and_geometry_distinct() -> None:
    scope = _MassPass()
    for value in (recipe(), recipe(".5", ".6"), recipe(width=".75")):
        scope.add(value, "onsite")
    assert scope.totals("onsite") == _MassTotals(F("2.5"), F(".8"), F("3.3"))
    assert len(scope._values) == 3


def test_equal_distinct_objects_keep_strong_references_and_separate_buckets() -> None:
    first, equal = recipe(), recipe()
    scope = _MassPass()
    scope.add(first, "onsite")
    scope.add(equal, "shipped")
    assert first is not equal
    assert scope._identities[id(first)][0] is first
    assert scope._identities[id(equal)][0] is equal
    assert scope.totals("onsite") == scope.totals("shipped") == _MassTotals(F(1), F(".1"), F("1.1"))
    assert scope.totals("disposal") == _MassTotals(F(0), F(0), F(0))


@pytest.mark.parametrize("alias", [True, 1, 1.0])
def test_equal_numeric_alias_rejects_before_recipe_hashing(alias: Any) -> None:
    good = recipe()
    bad = replace(good, contents_mass_kg=alias)
    assert good == bad and hash(good) == hash(bad)
    with pytest.raises(StockError):
        total(good, bad)


@pytest.mark.parametrize("field", ["dimensions", "primary_tare_kg"])
def test_equal_geometry_and_tare_aliases_reject(field: str) -> None:
    good, bad = recipe(tare="0", width="1"), recipe(tare="0", width="1")
    object.__setattr__(bad, field, (True, F(1), F(1)) if field == "dimensions" else False)
    assert good == bad
    with pytest.raises(StockError):
        total(good, bad)


def test_mass_or_type_changes_between_calls_cannot_reuse_previous_validation() -> None:
    value = recipe()
    assert total(value) == _MassTotals(F(1), F(".1"), F("1.1"))
    object.__setattr__(value, "contents_mass_kg", F(2))
    assert total(value) == _MassTotals(F(2), F(".1"), F("2.1"))
    object.__setattr__(value, "contents_mass_kg", True)
    with pytest.raises(StockError):
        total(value)
