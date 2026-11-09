"""One replay ledger issues exact original HU claims and completed N1 transfer commands."""

from app.v3.coordinator_run_inventory import InventoryJournal
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.relocation_models import RelocationPlan, RelocationProfile
from app.v3.stock_claims import StockClaim
from app.v3.stock_models import StockDelta


class RelocationInventory(InventoryJournal):
    def __init__(self, profile: RelocationProfile, plans: tuple[RelocationPlan, ...]) -> None:
        super().__init__(profile.coordinator)
        self.relocations = {p.job.job_id: p for p in plans}

    def _acquire(self, key: str) -> StockClaim:
        if key not in self.relocations:
            return super()._acquire(key)
        plan = self.relocations[key]
        if self.ledger.contents(plan.job.hu_id).container.owner_id != plan.job.from_slot_id:
            raise ValueError("Relocation claim lacks its original actual source")
        return self.ledger.reserve_hu(
            "relocation:" + key, key, self.ledger.revision, plan.job.hu_id
        )

    def _release(self, event: ReceiptFlowEvent) -> None:
        if event.order_id not in self.relocations:
            super()._release(event)
            return
        job = self.relocations[event.order_id].job
        if event.released_claim_id != "relocation:" + job.job_id:
            raise ValueError("Relocation released another inventory claim")
        if self.ledger.contents(job.hu_id).container.owner_id != job.to_slot_id:
            raise ValueError("Relocation claim release precedes actual place")
        self.ledger.release_claim("relocation:" + job.job_id, job.job_id)

    def _delta(self, event: FlowEvent) -> StockDelta:
        if event.order_id not in self.relocations:
            return super()._delta(event)
        job = self.relocations[event.order_id].job
        owners = {"relocation_taken": "actor:" + job.actor_id, "relocation_placed": job.to_slot_id}
        if event.kind not in owners:
            raise ValueError("Unknown relocation stock command")
        return self.ledger.transfer_whole_hu(
            job.job_id + ":" + event.kind,
            self.ledger.revision,
            job.hu_id,
            owners[event.kind],
            claim_id="relocation:" + job.job_id,
        )
