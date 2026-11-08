"""Receipt job bookkeeping only; stock custody and actors have no duplicated state."""

from dataclasses import dataclass

from app.v3.receipt_flow_models import ReceiptOffer, ReceiptView


@dataclass
class ReceiptState:
    offer: ReceiptOffer
    status: str = "unreleased"
    actor_id: str | None = None
    buffer_owner_id: str | None = None
    admitted_tick: int | None = None
    credited_tick: int | None = None
    placed_tick: int | None = None
    returned_tick: int | None = None
    wait_reason: str | None = None
    buffer_released: bool = False

    def view(self, tick: int) -> ReceiptView:
        paid = (
            0
            if self.admitted_tick is None
            else min(tick, self.returned_tick or tick) - self.admitted_tick
        )
        return ReceiptView(
            self.offer.definition.receipt_id,
            self.status,
            self.actor_id,
            self.buffer_owner_id,
            self.admitted_tick,
            self.credited_tick,
            self.placed_tick,
            self.returned_tick,
            self.wait_reason,
            paid,
        )
