"""Finite predicted-offer allocations, without actual work, receipts or ledger credit."""

from dataclasses import dataclass
from typing import Literal

from app.v3.offer_projection_models import OfferProjectionInputs
from app.v3.outbound_shift_models import BaselinePlacement
from app.v3.outbound_stock_models import StockAllocation, StockHU

VERSION = "qoima-offer-forecast-stock-0.1.0"
POLICY = "original_only_visible_shortage"
SCOPE = "predicted_outbound_whole_hu_finite_original_stock"


@dataclass(frozen=True, slots=True)
class ForecastBoundStock:
    projection: OfferProjectionInputs
    original_stock: tuple[StockHU, ...]
    declared_receipts: tuple[StockHU, ...]
    initial_placements: tuple[BaselinePlacement, ...]
    allocations: tuple[StockAllocation, ...]
    source_stock_hash: str
    frozen_bytes: bytes
    input_hash: str

    @property
    def operational_admission(self) -> Literal[False]:
        return False

    @property
    def full_n1_acceptance(self) -> Literal[False]:
        return False

    @property
    def actual_test_stream(self) -> Literal[False]:
        return False
