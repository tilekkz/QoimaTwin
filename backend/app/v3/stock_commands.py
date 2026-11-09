"""Versioned exact command values for opt-in accounting retries, not motion permits."""

from dataclasses import dataclass

from .stock_claims import identity
from .stock_receipts import ReceiptDefinition, validate_receipt
from .stock_validation import require

STOCK_COMMAND_VERSION = "qoima-stock-command-v2-proposal"


@dataclass(frozen=True, slots=True)
class ReceiveHUCommand:
    transaction_id: str
    expected_revision: int
    completed_tick: int
    receipt: ReceiptDefinition
    owner_id: str


@dataclass(frozen=True, slots=True)
class TransferHUCommand:
    transaction_id: str
    expected_revision: int
    completed_tick: int
    hu_id: str
    owner_id: str
    claim_id: str | None = None


@dataclass(frozen=True, slots=True)
class ShipHUCommand:
    transaction_id: str
    expected_revision: int
    completed_tick: int
    hu_id: str
    owner_id: str
    claim_id: str | None = None


StockCommand = ReceiveHUCommand | TransferHUCommand | ShipHUCommand


def validate_command(command: StockCommand) -> None:
    require(type(command) in {ReceiveHUCommand, TransferHUCommand, ShipHUCommand}, "typed command")
    identity(command.transaction_id)
    identity(command.owner_id)
    require(type(command.expected_revision) is int and command.expected_revision >= 0, "revision")
    require(type(command.completed_tick) is int and command.completed_tick >= 0, "completion tick")
    if isinstance(command, ReceiveHUCommand):
        validate_receipt(command.receipt)
    else:
        identity(command.hu_id)
        if command.claim_id is not None:
            identity(command.claim_id)
