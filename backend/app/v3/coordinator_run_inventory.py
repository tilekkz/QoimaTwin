"""Replay one physical inventory through public CAS commands and explicit claim facts."""

from app.v3.coordinator_models import CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_native_decode import encode
from app.v3.coordinator_run_stock_commands import StockCommands
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.stock_claims import StockClaim
from app.v3.stock_models import StockDelta
from app.v3.whole_flow_models import WholeFlowEvent


def same(actual: object, expected: object, message: str) -> None:
    if encode(actual) != encode(expected):
        raise ValueError(message)


class InventoryJournal(StockCommands):
    def __init__(self, profile: CoordinatorProfile) -> None:
        super().__init__(profile)
        self.assignments: dict[str, tuple[str, str]] = {}
        self.pending_pick: tuple[str, int] | None = None
        self.pending_whole: tuple[str, int] | None = None

    def apply(self, event: FlowEvent) -> None:
        self._pending(event)
        self._remember(event)
        if isinstance(event, ReceiptFlowEvent):
            if event.kind == "inventory_claim_acquired":
                same(
                    event.inventory_claim, self._acquire(event.order_id), "Inventory claim differs"
                )
            elif event.inventory_claim is not None:
                raise ValueError("Unexpected inventory claim payload")
            if event.kind == "inventory_claim_released":
                self._release(event)
            elif event.released_claim_id is not None:
                raise ValueError("Unexpected released claim payload")
        if event.delta is not None:
            same(event.delta, self._delta(event), "Stock delta differs from declared command")

    def _pending(self, event: FlowEvent) -> None:
        if self.pending_pick is not None and (
            (event.order_id, event.tick) != self.pending_pick or event.kind != "picked"
        ):
            raise ValueError("Consumed pick claim must be followed by its exact stock delta")
        if self.pending_whole is not None:
            if (event.order_id, event.tick) != self.pending_whole:
                raise ValueError("Consumed whole claim must be acknowledged immediately")
            if event.kind != "inventory_claim_released":
                raise ValueError("Consumed whole claim lacks its release fact")

    def _remember(self, event: FlowEvent) -> None:
        actor = buffer = None
        if isinstance(event, WholeFlowEvent) and event.whole_order is not None:
            view = event.whole_order
            actor, buffer = view.actor_id, view.buffer_owner_id
            if event.order_id not in self.whole:
                raise ValueError("Unknown whole inventory job")
            port = self.whole_ports[self.whole[event.order_id].port_id]
            permitted, actors = port.buffer_ids, port.shipper_ids
        elif isinstance(event, ReceiptFlowEvent) and event.receipt is not None:
            actor, buffer = event.receipt.actor_id, event.receipt.buffer_owner_id
            if event.order_id not in self.receipts:
                raise ValueError("Unknown receipt inventory job")
            receipt_port = self.receipt_ports[self.receipts[event.order_id].port_id]
            permitted, actors = receipt_port.buffer_ids, receipt_port.receiver_ids
        else:
            return
        if actor is None and buffer is None:
            if event.order_id in self.assignments:
                raise ValueError("Admitted inventory assignment disappeared")
            return
        if actor not in actors or buffer not in permitted:
            raise ValueError("Inventory actor or buffer is not permitted by the selected port")
        if actor is None or buffer is None:
            raise ValueError("Inventory assignment must specify actor and buffer")
        pair = (actor, buffer)
        same(
            pair, self.assignments.setdefault(event.order_id, pair), "Inventory assignment changed"
        )

    def _acquire(self, key: str) -> StockClaim:
        revision = self.ledger.revision
        if key in self.units:
            order = self.units[key]
            return self.ledger.reserve_units(
                "pick:" + key,
                key,
                revision,
                order.source_hu,
                tuple(p.unit_id for p in order.carrier_placements),
            )
        if key in self.receipts:
            hu, prefix = self.receipts[key].definition.hu_id, "receipt:"
        elif key in self.whole:
            hu, prefix = self.whole[key].hu_id, "whole:"
        else:
            raise ValueError("Unknown inventory claimant")
        return self.ledger.reserve_hu(prefix + key, key, revision, hu)

    def _release(self, event: ReceiptFlowEvent) -> None:
        key = event.order_id
        prefix = "pick:" if key in self.units else "receipt:" if key in self.receipts else "whole:"
        if event.released_claim_id != prefix + key:
            raise ValueError("Released inventory claim differs from its job")
        if key in self.units:
            if not any(c.claim_id == "pick:" + key for c in self.ledger.claims):
                raise ValueError("Released pick claim was never acquired")
            self.pending_pick = (key, event.tick)
        elif key in self.receipts:
            offer = self.receipts[key]
            if (
                self.ledger.contents(offer.definition.hu_id).container.owner_id
                != offer.slot_owner_id
            ):
                raise ValueError("Receipt claim released before actual putaway")
            self.ledger.release_claim(prefix + key, key)
        elif self.pending_whole == (key, event.tick):
            self.pending_whole = None
        else:
            raise ValueError("Whole claim release lacks actual shipment")

    def _delta(self, event: FlowEvent) -> StockDelta:
        key = event.order_id
        if key in self.units:
            if event.kind == "picked" and self.pending_pick != (key, event.tick):
                raise ValueError("Pick delta lacks explicit consumed claim fact")
            delta = self.unit_delta(event)
            if event.kind == "picked":
                self.pending_pick = None
            return delta
        if key not in self.assignments:
            raise ValueError("Stock delta lacks admitted physical assignment")
        actor, buffer = self.assignments[key]
        if key in self.receipts:
            return self.receipt_delta(event, actor, buffer)
        if key in self.whole:
            delta = self.whole_delta(event, actor, buffer)
            if event.kind == "whole_shipped":
                self.pending_whole = (key, event.tick)
            return delta
        raise ValueError("Stock delta belongs to an unknown job")

    def check(self, state: CoordinatorSnapshot) -> None:
        if self.pending_pick is not None or self.pending_whole is not None:
            raise ValueError("Settled inventory contains an incomplete claim transition")
        same(state.stock, self.ledger.snapshot(), "Captured stock differs from inventory journal")
        same(state.inventory, self.ledger.inventory_snapshot(), "Captured inventory differs")
        same(state.balance, self.ledger.balance(), "Captured inventory balance differs")
