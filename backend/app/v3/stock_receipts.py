"""Append-only accounting definitions; physical operation admission belongs to the coordinator."""

from dataclasses import dataclass

from .stock_claims import StockClaim, identity
from .stock_models import (
    Container,
    ContainerRecipe,
    StockDelta,
    StockSnapshot,
    UnitRecipe,
    UnitToken,
)
from .stock_validation import require


@dataclass(frozen=True, slots=True)
class ReceiptDefinition:
    receipt_id: str
    hu_id: str
    sku_id: str
    lot_id: str
    quantity_units: int


@dataclass(frozen=True, slots=True)
class ReceiptDelta(StockDelta):
    receipt: ReceiptDefinition
    created_tokens: tuple[UnitToken, ...]


@dataclass(frozen=True, slots=True)
class InventorySnapshot(StockSnapshot):
    registered_receipts: tuple[ReceiptDefinition, ...]
    claims: tuple[StockClaim, ...]
    claim_generation: int


def validate_receipt(value: ReceiptDefinition) -> None:
    require(type(value) is ReceiptDefinition, "typed receipt definition required")
    for key in (value.receipt_id, value.hu_id, value.sku_id, value.lot_id):
        identity(key)
    require(type(value.quantity_units) is int and value.quantity_units > 0, "receipt quantity")


def receipt_recipes(
    sku_id: str, tokens: dict[str, UnitToken], containers: dict[str, Container]
) -> tuple[UnitRecipe, ContainerRecipe]:
    units = [unit for unit in tokens.values() if unit.sku_id == sku_id]
    require(bool(units), "unknown source SKU")
    unit, wrapper = units[0].recipe, containers[units[0].origin_hu].recipe
    require(
        all(t.recipe == unit and containers[t.origin_hu].recipe == wrapper for t in units),
        "conflicting source SKU recipe",
    )
    return unit, wrapper


def receipt_tokens(value: ReceiptDefinition, recipe: UnitRecipe) -> tuple[UnitToken, ...]:
    return tuple(
        UnitToken(
            f"{value.hu_id}:unit:{ordinal:04d}",
            value.hu_id,
            value.sku_id,
            value.lot_id,
            ordinal,
            recipe,
        )
        for ordinal in range(1, value.quantity_units + 1)
    )
