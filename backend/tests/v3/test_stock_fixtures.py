"""Explicit synthetic materials; these are test recipes, never warehouse defaults."""

from fractions import Fraction as F

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import (
    Container,
    ContainerRecipe,
    Placement,
    StockOwner,
    StockSeed,
    UnitRecipe,
    UnitToken,
)


def recipe(kind: str = "carrier", *, rating: F = F(10)) -> ContainerRecipe:
    return ContainerRecipe(
        kind,
        "hand fixture, ADR0041",
        kind,
        (F(1), F(1), F(1)),
        (F(".8"), F(".8"), F(".8")),
        F(".20") if kind == "carrier" else F(".05"),
        rating,
        24,
        ("SMALL_CARTON",),
        F(0),
    )


def source_seed_fixture() -> StockSeed:
    unit = UnitRecipe("SMALL_CARTON", (F(".06"), F(".04"), F(".04")), F(".03"), F(".005"))
    units = tuple(UnitToken(f"U{i}", "HU1", "SKU1", "LOT1", i, unit) for i in range(1, 25))
    wrapper = ContainerRecipe(
        "source",
        "C02 small hand fixture",
        "source_wrapper",
        (F(".32"), F(".24"), F(".24")),
        None,
        F(".1"),
        F(".94"),
        24,
        ("SMALL_CARTON",),
        F(0),
    )
    return StockSeed(units, (Container("HU1", wrapper, "slot"),), (StockOwner("slot", "slot", 1),))


def ledger(*, parcel_rating: F = F(10)) -> StockLedger:
    owners = tuple(
        StockOwner(name, kind, cap)
        for name, kind, cap in (
            ("bench", "workstation", 4),
            ("ship", "shipped", 10),
            ("waste", "disposal", 10),
            ("single", "workstation", 1),
        )
    )
    materials = (
        Container("C1", recipe(), "bench"),
        Container("C2", recipe(), "bench"),
        Container("P1", recipe("package", rating=parcel_rating), "bench"),
    )
    return StockLedger(source_seed_fixture(), owners=owners, materials=materials)


def placements(*ids: int) -> tuple[Placement, ...]:
    return tuple(Placement(f"U{n}", (F(i, 15), F(0), F(0))) for i, n in enumerate(ids))
