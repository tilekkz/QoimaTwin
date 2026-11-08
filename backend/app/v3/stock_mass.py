"""Exact mass aggregation scoped to one full scan, never inventory authority."""

from collections import Counter
from fractions import Fraction
from typing import NamedTuple

from .stock_models import UnitRecipe
from .stock_validation import exact, require


class _MassTotals(NamedTuple):
    net: Fraction
    primary: Fraction
    gross: Fraction


def _validate_recipe(recipe: UnitRecipe) -> None:
    require(type(recipe) is UnitRecipe, "exact unit recipe required")
    require(type(recipe.archetype_id) is str and bool(recipe.archetype_id), "unit archetype")
    require(type(recipe.dimensions) is tuple and len(recipe.dimensions) == 3, "unit dimensions")
    for value in (*recipe.dimensions, recipe.contents_mass_kg):
        exact(value, positive=True)
    exact(recipe.primary_tare_kg)


class _MassPass:
    """Retain every recipe identity; discard all counts when the caller returns."""

    def __init__(self) -> None:
        self._identities: dict[int, tuple[UnitRecipe, int]] = {}
        self._values: dict[UnitRecipe, int] = {}
        self._masses: list[_MassTotals] = []
        self._counts: dict[str, Counter[int]] = {}

    def _intern(self, recipe: UnitRecipe) -> int:
        found = self._identities.get(id(recipe))
        if found is not None:
            require(found[0] is recipe, "recipe identity reuse")
            return found[1]
        _validate_recipe(recipe)
        index = self._values.get(recipe)
        if index is None:
            index = len(self._masses)
            self._values[recipe] = index
            self._masses.append(
                _MassTotals(recipe.contents_mass_kg, recipe.primary_tare_kg, recipe.gross_mass_kg)
            )
        self._identities[id(recipe)] = (recipe, index)
        return index

    def add(self, recipe: UnitRecipe, bucket: str) -> None:
        index = self._intern(recipe)
        if bucket not in self._counts:
            self._counts[bucket] = Counter()
        self._counts[bucket][index] += 1

    def totals(self, bucket: str) -> _MassTotals:
        net, primary, gross = Fraction(0), Fraction(0), Fraction(0)
        for index, count in self._counts.get(bucket, {}).items():
            mass = self._masses[index]
            net += count * mass.net
            primary += count * mass.primary
            gross += count * mass.gross
        return _MassTotals(net, primary, gross)
