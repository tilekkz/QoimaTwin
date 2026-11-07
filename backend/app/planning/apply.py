"""Apply and verify plan artifacts: lots move whole with their SKU, the buffer ends empty."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.contracts.assignment import Assignment, InitialLot
from app.contracts.layout import Layout
from app.planning.abc import active_lots
from app.planning.errors import PlanningInputError
from app.planning.models import PlanArtifact, TransferRecord
from app.storage.canonical_json import sha256_hex


def assignment_hash(assignment: Assignment) -> str:
    """Same value as the run identity "assignment" hash (ADR 0008): placement plus lots."""
    lots = sorted(assignment.initial_lots, key=lambda lot: lot.lot_id)
    return sha256_hex(
        {
            "active": dict(assignment.active_assignment),
            "lots": [lot.model_dump(mode="json") for lot in lots],
        }
    )


def plan_content_hash(plan: PlanArtifact) -> str:
    """Hash of every plan field except plan_id itself; no test results exist in a plan."""
    data: dict[str, Any] = plan.model_dump(mode="json")
    data.pop("plan_id")
    return sha256_hex(data)


def replay_transfers(
    baseline: Assignment, transfers: Sequence[TransferRecord], buffer: str, new_id: str
) -> Assignment:
    """Replay transfer records on the active lots; no lot is created, split or duplicated."""
    if not transfers:
        return baseline
    occupancy: dict[str, InitialLot] = dict(active_lots(baseline))
    for record in transfers:
        lot = occupancy.get(record.from_location)
        if lot is None or (lot.lot_id, lot.quantity) != (record.lot_id, record.quantity):
            raise PlanningInputError(f"{record.transfer_id}: {record.lot_id} is not at the source")
        if record.to_location in occupancy:
            raise PlanningInputError(f"{record.transfer_id}: destination is occupied")
        del occupancy[record.from_location]
        occupancy[record.to_location] = lot
    if buffer in occupancy or set(occupancy) != set(baseline.active_assignment):
        raise PlanningInputError("relocation must end with an empty buffer and the same slots")
    return _rebuilt(baseline, {lot.lot_id: slot for slot, lot in occupancy.items()}, new_id)


def _rebuilt(baseline: Assignment, slot_of_lot: dict[str, str], new_id: str) -> Assignment:
    lots = []
    active: dict[str, str] = {}
    for lot in baseline.initial_lots:
        data = lot.model_dump(mode="json")
        if lot.lot_id in slot_of_lot:
            data["slot_id"] = slot_of_lot[lot.lot_id]
            active[data["slot_id"]] = lot.sku_id
        lots.append(data)
    data = baseline.model_dump(mode="json")
    data.update(
        assignment_id=new_id,
        provenance={
            "kind": "relocation_plan",
            "note": f"swaps applied to {baseline.assignment_id}",
        },
        active_assignment=dict(sorted(active.items())),
        initial_lots=lots,
    )
    return Assignment.from_data(data)


def apply_plan(baseline: Assignment, plan: PlanArtifact, layout: Layout) -> Assignment:
    """Candidate assignment after the plan; the baseline must be the planned one."""
    if assignment_hash(baseline) != plan.baseline_assignment_hash:
        raise PlanningInputError("plan was made for a different baseline assignment")
    result = replay_transfers(
        baseline,
        plan.relocation.transfers,
        layout.relocation_buffer_node_id,
        plan.final_assignment.assignment_id,
    )
    if result != plan.final_assignment:
        raise PlanningInputError("replayed transfers disagree with the plan's final assignment")
    return result
