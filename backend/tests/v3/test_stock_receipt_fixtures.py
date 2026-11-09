"""Hand-declared receipt inputs; recipe numbers are C02 arithmetic, not engine output."""

from fractions import Fraction as F

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container, StockOwner
from app.v3.stock_receipts import ReceiptDefinition
from tests.v3.test_stock_fixtures import recipe, source_seed_fixture


def receipt(
    *,
    receipt_id: str = "R2",
    hu_id: str = "HU2",
    sku_id: str = "SKU1",
    lot_id: str = "LOT2",
    quantity_units: int = 24,
) -> ReceiptDefinition:
    return ReceiptDefinition(receipt_id, hu_id, sku_id, lot_id, quantity_units)


def receiving_ledger() -> StockLedger:
    owners = tuple(
        StockOwner(identity, kind, capacity)
        for identity, kind, capacity in (
            ("slot2", "slot", 1),
            ("buffer", "buffer", 1),
            ("worker", "worker", 1),
            ("vehicle", "vehicle", 1),
            ("ship", "shipped", 10),
            ("materials", "material", 2),
            ("work", "workstation", 1),
        )
    )
    materials = (
        Container("C1", recipe(), "materials"),
        Container("P1", recipe("package"), "materials"),
    )
    return StockLedger(source_seed_fixture(), owners=owners, materials=materials)


def received_three() -> tuple[tuple[str, tuple[F, F, F]], ...]:
    return tuple((f"HU2:unit:{i + 1:04d}", (F(i, 15), F(0), F(0))) for i in range(3))
