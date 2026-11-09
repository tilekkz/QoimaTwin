"""Materialized scenario: orders, receipts and provenance (contracts/scenario.schema.json)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt, model_validator

from app.contracts.base import FrozenModel, NonEmptyStr


class Provenance(FrozenModel):
    kind: Literal["synthetic", "historical_partial_baskets", "synthetic_fixture"]
    generator_version: NonEmptyStr
    seed: int
    source_notes: NonEmptyStr
    orders_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class OrderLine(FrozenModel):
    sku_id: NonEmptyStr
    quantity: PositiveInt


class Order(FrozenModel):
    order_id: NonEmptyStr
    arrival_s: NonNegativeFloat
    lines: tuple[OrderLine, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_skus(self) -> Order:
        skus = [line.sku_id for line in self.lines]
        if len(skus) != len(set(skus)):
            raise ValueError(f"order {self.order_id} repeats a SKU line")
        return self

    @property
    def units(self) -> int:
        return sum(line.quantity for line in self.lines)


class Receipt(FrozenModel):
    receipt_id: NonEmptyStr
    arrival_s: NonNegativeFloat
    sku_id: NonEmptyStr
    quantity: PositiveInt


class Scenario(FrozenModel):
    schema_version: Literal["2.0"]
    scenario_id: NonEmptyStr
    layout_version: NonEmptyStr
    provenance: Provenance
    horizon_s: PositiveFloat
    orders: tuple[Order, ...]
    receipts: tuple[Receipt, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Scenario:
        order_ids = [o.order_id for o in self.orders]
        receipt_ids = [r.receipt_id for r in self.receipts]
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("duplicate order_id")
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("duplicate receipt_id")
        late = [o.order_id for o in self.orders if o.arrival_s >= self.horizon_s]
        late += [r.receipt_id for r in self.receipts if r.arrival_s >= self.horizon_s]
        if late:
            raise ValueError(f"arrivals at or after horizon: {late[:5]}")
        return self
