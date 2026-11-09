"""Fresh pinned storage capacities; usable volume is exact dimensional multiplication."""

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.inputs import load_v3_bundle
from app.v3.storage_fullness_models import ModuleCapacity, SlotCapacity
from app.v3.storage_fullness_validation import require

STORAGE_PATH = "docs/v3/contract-proposals/storage-slots-v3.json"


def _slot(row: dict[str, Any]) -> SlotCapacity:
    x, y, z = (Fraction(value) for value in row["usable_dimensions_xyz_m"])
    return SlotCapacity(
        row["slot_id"],
        row["module_id"],
        row["zone_id"],
        row["active_pick_candidate"],
        row["reserve_only"],
        row["retrieval_blocked"],
        row["max_handling_units"],
        Fraction(row["max_payload_kg"]),
        x * y * z,
    )


def source_capacities(
    profile: CoordinatorProfile,
) -> tuple[tuple[SlotCapacity, ...], tuple[ModuleCapacity, ...]] | None:
    flow = profile.world.receipts.flow
    if flow.source_revision is None:
        return None
    source = load_v3_bundle(Path(__file__).resolve().parents[2] / "data/v3-proposal")
    require(
        type(flow.source_revision) is str and flow.source_revision == source.source_revision,
        "source revision differs",
    )
    require(type(flow.source_hashes) is tuple, "source fingerprints must be immutable")
    require(
        all(
            type(pair) is tuple and len(pair) == 2 and all(type(value) is str for value in pair)
            for pair in flow.source_hashes
        ),
        "source fingerprint pairs require immutable exact strings",
    )
    hashes = dict(flow.source_hashes)
    require(len(hashes) == len(flow.source_hashes), "duplicate source fingerprint")
    require(
        all(hashes.get(row.path) == row.raw_sha256 for row in source.source_inventory),
        "source fingerprints differ",
    )
    document = json.loads(source.documents[STORAGE_PATH].canonical_bytes, parse_float=Fraction)
    slots = tuple(_slot(row) for row in document["slots"])
    modules = tuple(
        ModuleCapacity(
            row["module_id"], row["max_handling_units"], Fraction(row["max_module_payload_kg"])
        )
        for row in document["modules"]
    )
    owners = tuple(owner for owner in (*flow.stock.owners, *flow.owners) if owner.kind == "slot")
    require(len(owners) == len(slots), "source storage owner coverage differs")
    counts = {owner.owner_id: owner.capacity for owner in owners}
    require(len(counts) == len(owners), "duplicate storage owner")
    require(
        all(
            type(counts.get(slot.slot_id)) is int and counts.get(slot.slot_id) == slot.hu_capacity
            for slot in slots
        ),
        "source storage owner capacity differs",
    )
    return slots, modules
