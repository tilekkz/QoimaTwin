"""No float tolerances, implicit rotations, stacking permission or material creation."""

from collections import Counter, defaultdict
from fractions import Fraction

from .stock_models import (
    Container,
    ContainerContents,
    ContainerRecipe,
    StockError,
    StockOwner,
    StockSeed,
    UnitToken,
    Vec3,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StockError(message)


def exact(value: Fraction, *, positive: bool = False) -> None:
    require(type(value) is Fraction, "exact Fraction required")
    require(value > 0 if positive else value >= 0, "invalid physical quantity")


def vector(value: Vec3, *, positive: bool = True) -> None:
    require(isinstance(value, tuple) and len(value) == 3, "three exact dimensions required")
    for item in value:
        exact(item, positive=positive)


def validate_owner(owner: StockOwner) -> None:
    require(bool(owner.owner_id.strip()), "empty owner id")
    require(
        owner.kind
        in {
            "slot",
            "workstation",
            "material",
            "shipped",
            "disposal",
            "buffer",
            "worker",
            "vehicle",
        },
        "owner kind",
    )
    require(type(owner.capacity) is int and owner.capacity > 0, "owner capacity")


def validate_container(container: Container, owners: dict[str, StockOwner]) -> None:
    r = container.recipe
    require(
        bool(container.container_id.strip()) and container.owner_id in owners, "unknown owner/id"
    )
    require(bool(r.recipe_id.strip()) and bool(r.provenance.strip()), "recipe provenance required")
    require(r.kind in {"source_wrapper", "carrier", "package"}, "unsupported container kind")
    vector(r.outer)
    exact(r.tare_kg)
    exact(r.max_gross_kg, positive=True)
    exact(r.clearance_m)
    require(r.tare_kg <= r.max_gross_kg, "empty material exceeds gross rating")
    require(type(r.max_units) is int and r.max_units > 0, "unit capacity")
    require(
        type(r.allowed_archetypes) is tuple
        and bool(r.allowed_archetypes)
        and all(r.allowed_archetypes),
        "allowed archetypes required",
    )
    if r.kind == "source_wrapper":
        require(r.inner is None and container.sealed_for is None, "source wrapper recipe")
    else:
        require(r.inner is not None, "explicit inner dimensions required")
        assert r.inner is not None
        vector(r.inner)
        require(all(i <= o for i, o in zip(r.inner, r.outer, strict=True)), "inner exceeds outer")
        require(all(2 * r.clearance_m < i for i in r.inner), "clearance consumes inner volume")


def validate_unit(unit: UnitToken, containers: dict[str, Container]) -> None:
    require(all((unit.unit_id, unit.origin_hu, unit.sku_id, unit.lot_id)), "unit identity required")
    require(type(unit.ordinal) is int and unit.ordinal > 0, "unit ordinal")
    require(unit.origin_hu in containers, "unknown origin HU")
    require(containers[unit.origin_hu].recipe.kind == "source_wrapper", "origin is not source HU")
    require(bool(unit.recipe.archetype_id), "unit archetype required")
    vector(unit.recipe.dimensions)
    exact(unit.recipe.contents_mass_kg, positive=True)
    exact(unit.recipe.primary_tare_kg)


def validate_seed(
    seed: StockSeed, containers: dict[str, Container], owners: dict[str, StockOwner]
) -> None:
    catalog: dict[str, ContainerRecipe] = {}
    groups: dict[str, list[UnitToken]] = defaultdict(list)
    for container in containers.values():
        recipe = container.recipe
        require(
            recipe.recipe_id not in catalog or catalog[recipe.recipe_id] == recipe,
            "conflicting recipe identity",
        )
        catalog[recipe.recipe_id] = recipe
    for token in seed.units:
        groups[token.origin_hu].append(token)
    for container in seed.containers:
        owner = owners[container.owner_id]
        require(owner.kind == "slot" and owner.capacity == 1, "initial source slot required")
        units = groups[container.container_id]
        require(len(units) == container.recipe.max_units, "initial source recipe quantity")
        require({u.ordinal for u in units} == set(range(1, len(units) + 1)), "source ordinal range")
        require(
            len({(u.sku_id, u.lot_id, u.recipe) for u in units}) == 1,
            "conflicting source HU ancestry recipe",
        )


def overlap(a: Vec3, size_a: Vec3, b: Vec3, size_b: Vec3) -> bool:
    return all(a[i] < b[i] + size_b[i] and b[i] < a[i] + size_a[i] for i in range(3))


def validate_contents(contents: ContainerContents) -> None:
    recipe = contents.container.recipe
    require(len(contents.units) <= recipe.max_units, "unit capacity exceeded")
    require(contents.gross_mass_kg <= recipe.max_gross_kg, "gross capacity exceeded")
    for unit in contents.units:
        require(unit.token.recipe.archetype_id in recipe.allowed_archetypes, "cargo kind forbidden")
    if recipe.kind == "source_wrapper":
        require(all(u.position is None for u in contents.units), "source packing is opaque")
        require(
            all(u.token.origin_hu == contents.container.container_id for u in contents.units),
            "foreign unit inside source wrapper",
        )
        return
    assert recipe.inner is not None
    for i, unit in enumerate(contents.units):
        position = unit.position
        require(position is not None, "placement required")
        assert position is not None
        vector(position, positive=False)
        size = unit.token.recipe.dimensions
        require(position[1] == 0, "only floor-supported upright placements are supported")
        require(all(position[k] >= recipe.clearance_m for k in (0, 2)), "wall clearance")
        require(
            all(position[k] + size[k] + recipe.clearance_m <= recipe.inner[k] for k in range(3)),
            "unit exceeds usable bounds",
        )
        for other in contents.units[:i]:
            assert other.position is not None
            require(
                not overlap(position, size, other.position, other.token.recipe.dimensions),
                "overlapping units",
            )


def validate_owners(
    containers: dict[str, Container],
    owners: dict[str, StockOwner],
    whole_shipments: frozenset[str] = frozenset(),
) -> None:
    counts = Counter(c.owner_id for c in containers.values())
    for owner_id, count in counts.items():
        require(owner_id in owners, "unknown owner")
        require(count <= owners[owner_id].capacity, "owner capacity exceeded")
    for container in containers.values():
        kind = owners[container.owner_id].kind
        if kind == "slot":
            require(
                container.recipe.kind == "source_wrapper", "material slot admission unsupported"
            )
        if kind == "shipped":
            require(
                (container.recipe.kind == "package" and bool(container.sealed_for))
                or (
                    container.recipe.kind == "source_wrapper"
                    and container.container_id in whole_shipments
                ),
                "unsealed shipment",
            )
