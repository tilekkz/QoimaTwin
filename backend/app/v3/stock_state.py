"""Immutable physical views and mass accounting, independent of clocks or workers."""

from collections import Counter, defaultdict
from fractions import Fraction

from .stock_mass import _MassPass
from .stock_models import (
    Container,
    ContainerContents,
    PlacedUnit,
    StockBalance,
    StockOwner,
    UnitLocation,
    UnitToken,
)
from .stock_validation import exact, require, validate_contents, validate_owners


def contents_view(
    container: Container,
    locations: dict[str, UnitLocation],
    tokens: dict[str, UnitToken],
) -> ContainerContents:
    units = tuple(
        PlacedUnit(tokens[key], value.position)
        for key, value in sorted(locations.items())
        if value.container_id == container.container_id
    )
    scope = _MassPass()
    for unit in units:
        scope.add(unit.token.recipe, container.container_id)
    gross = container.recipe.tare_kg + scope.totals(container.container_id).gross
    return ContainerContents(container, units, gross)


def gross_masses(
    containers: dict[str, Container],
    locations: dict[str, UnitLocation],
    tokens: dict[str, UnitToken],
) -> dict[str, Fraction]:
    """Project current per-container mass in one local pass, including empty tare."""
    require(locations.keys() == tokens.keys(), "unit conservation violation")
    scope = _MassPass()
    for key, location in locations.items():
        require(key == location.unit_id, "unit location identity mismatch")
        require(location.container_id in containers, "unknown physical container")
        scope.add(tokens[key].recipe, location.container_id)
    result: dict[str, Fraction] = {}
    for key, container in containers.items():
        require(key == container.container_id, "container identity mismatch")
        exact(container.recipe.tare_kg)
        result[key] = container.recipe.tare_kg + scope.totals(key).gross
    return result


def check_state(
    containers: dict[str, Container],
    locations: dict[str, UnitLocation],
    tokens: dict[str, UnitToken],
    owners: dict[str, StockOwner],
    whole_shipments: frozenset[str] = frozenset(),
) -> None:
    require(locations.keys() == tokens.keys(), "unit conservation violation")
    grouped: dict[str, list[PlacedUnit]] = defaultdict(list)
    scope = _MassPass()
    for key, location in locations.items():
        require(key == location.unit_id, "unit location identity mismatch")
        require(location.container_id in containers, "unknown physical container")
        grouped[location.container_id].append(PlacedUnit(tokens[key], location.position))
        scope.add(tokens[key].recipe, location.container_id)
    validate_owners(containers, owners, whole_shipments)
    actual_shipped = {
        c.container_id
        for c in containers.values()
        if c.recipe.kind == "source_wrapper" and owners[c.owner_id].kind == "shipped"
    }
    require(actual_shipped == whole_shipments, "whole shipment admission mismatch")
    for key, container in containers.items():
        require(key == container.container_id, "container identity mismatch")
        require(container.recipe.kind == "package" or container.sealed_for is None, "invalid seal")
        units = tuple(grouped[key])
        gross = container.recipe.tare_kg + scope.totals(key).gross
        view = ContainerContents(container, units, gross)
        validate_contents(view)
        if key in whole_shipments:
            require(len(units) == container.recipe.max_units, "whole shipment must remain intact")
        if owners[container.owner_id].kind == "disposal":
            require(not view.units, "units cannot be disposed")


def balances(
    containers: dict[str, Container],
    locations: dict[str, UnitLocation],
    tokens: dict[str, UnitToken],
    owners: dict[str, StockOwner],
) -> StockBalance:
    total: Counter[str] = Counter()
    onsite: Counter[str] = Counter()
    shipped: Counter[str] = Counter()
    tare = Fraction(0)
    scope = _MassPass()
    mass = {"onsite": Fraction(0), "shipped": Fraction(0), "disposal": Fraction(0)}
    for container in containers.values():
        kind = owners[container.owner_id].kind
        bucket = kind if kind in {"shipped", "disposal"} else "onsite"
        mass[bucket] += container.recipe.tare_kg
        tare += container.recipe.tare_kg
    for key, token in tokens.items():
        container = containers[locations[key].container_id]
        is_shipped = owners[container.owner_id].kind == "shipped"
        total[token.sku_id] += 1
        (shipped if is_shipped else onsite)[token.sku_id] += 1
        scope.add(token.recipe, "shipped" if is_shipped else "onsite")
    onsite_totals, shipped_totals = scope.totals("onsite"), scope.totals("shipped")
    mass["onsite"] += onsite_totals.gross
    mass["shipped"] += shipped_totals.gross
    return StockBalance(
        tuple(sorted(total.items())),
        tuple(sorted(onsite.items())),
        tuple(sorted(shipped.items())),
        onsite_totals.net + shipped_totals.net,
        onsite_totals.primary + shipped_totals.primary,
        tare,
        mass["onsite"],
        mass["shipped"],
        mass["disposal"],
    )
