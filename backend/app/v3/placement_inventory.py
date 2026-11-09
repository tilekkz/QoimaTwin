"""Read-only physical inventory seam; public callers must authenticate their own namespace."""

from typing import Protocol

from app.v3.outbound_stock_models import StockAllocation, StockHU


class PlacementInventory(Protocol):
    @property
    def original_stock(self) -> tuple[StockHU, ...]: ...

    @property
    def declared_receipts(self) -> tuple[StockHU, ...]: ...

    @property
    def allocations(self) -> tuple[StockAllocation, ...]: ...
