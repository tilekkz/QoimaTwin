"""Exact immutable values for the bounded unit and packaging ledger (ADR0041)."""

from dataclasses import dataclass
from fractions import Fraction

Vec3 = tuple[Fraction, Fraction, Fraction]


class StockError(ValueError):
    """Rejected transaction or invalid declared stock/materials; never a partial commit."""


@dataclass(frozen=True, slots=True)
class UnitRecipe:
    archetype_id: str
    dimensions: Vec3
    contents_mass_kg: Fraction
    primary_tare_kg: Fraction

    @property
    def gross_mass_kg(self) -> Fraction:
        return self.contents_mass_kg + self.primary_tare_kg


@dataclass(frozen=True, slots=True)
class UnitToken:
    unit_id: str
    origin_hu: str
    sku_id: str
    lot_id: str
    ordinal: int
    recipe: UnitRecipe


@dataclass(frozen=True, slots=True)
class ContainerRecipe:
    recipe_id: str
    provenance: str
    kind: str
    outer: Vec3
    inner: Vec3 | None
    tare_kg: Fraction
    max_gross_kg: Fraction
    max_units: int
    allowed_archetypes: tuple[str, ...]
    clearance_m: Fraction


@dataclass(frozen=True, slots=True)
class Container:
    container_id: str
    recipe: ContainerRecipe
    owner_id: str
    sealed_for: str | None = None


@dataclass(frozen=True, slots=True)
class StockOwner:
    owner_id: str
    kind: str
    capacity: int


@dataclass(frozen=True, slots=True)
class StockSeed:
    units: tuple[UnitToken, ...]
    containers: tuple[Container, ...]
    owners: tuple[StockOwner, ...]


@dataclass(frozen=True, slots=True)
class Placement:
    unit_id: str
    position: Vec3


@dataclass(frozen=True, slots=True)
class UnitLocation:
    unit_id: str
    container_id: str
    position: Vec3 | None


@dataclass(frozen=True, slots=True)
class PlacedUnit:
    token: UnitToken
    position: Vec3 | None


@dataclass(frozen=True, slots=True)
class ContainerContents:
    container: Container
    units: tuple[PlacedUnit, ...]
    gross_mass_kg: Fraction


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    revision: int
    containers: tuple[Container, ...]
    locations: tuple[UnitLocation, ...]


@dataclass(frozen=True, slots=True)
class StockDelta:
    transaction_id: str
    revision: int
    operation: str
    unit_ids: tuple[str, ...]
    before: tuple[ContainerContents, ...]
    after: tuple[ContainerContents, ...]


@dataclass(frozen=True, slots=True)
class StockBalance:
    units_by_sku: tuple[tuple[str, int], ...]
    onsite_units_by_sku: tuple[tuple[str, int], ...]
    shipped_units_by_sku: tuple[tuple[str, int], ...]
    contents_mass_kg: Fraction
    primary_tare_kg: Fraction
    container_tare_kg: Fraction
    onsite_mass_kg: Fraction
    shipped_mass_kg: Fraction
    disposed_mass_kg: Fraction

    @property
    def gross_mass_kg(self) -> Fraction:
        return self.onsite_mass_kg + self.shipped_mass_kg + self.disposed_mass_kg
