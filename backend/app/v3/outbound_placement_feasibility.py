"""Source feasibility precedes cost; offered receipt reservations never create stock."""

from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction as F
from typing import Any

from app.v3.admission import storage_admission
from app.v3.admission_models import Handler, StorageState
from app.v3.admission_source import SelectedCapability, SourceAdmissionCatalog
from app.v3.input_models import V3Bundle
from app.v3.outbound_placement_models import PlacementCandidate, PlacementChoices
from app.v3.outbound_stock_models import StockHU
from app.v3.placement_inventory import PlacementInventory
from app.v3.profile_build import document


def _ground(row: dict[str, Any]) -> bool:
    return (
        type(row["level"]) is int
        and row["level"] == 1
        and row["manual_pick_allowed"] is True
        and row["reserve_only"] is False
        and row["retrieval_blocked"] is False
        and row["max_handling_units"] == 1
        and row["service_node_id"] == row["access"]["worker_node_id"]
        and any(
            r["id"] == row["service_node_id"] and r["graph"] == "walk" and r["kind"] == "walk_node"
            for r in row["typed_access_references"]
        )
    )


def physical_reasons(
    bundle: V3Bundle,
    stock: PlacementInventory,
    choices: PlacementChoices,
    candidate: PlacementCandidate,
    hu: StockHU,
) -> tuple[str, ...]:
    storage = document(bundle, "storage-slots-v3.json")
    slots = {r["slot_id"]: r for r in storage["slots"]}
    if hu.initial_owner_id != candidate.from_slot_id:
        return ("ORIGINAL_SOURCE_MISMATCH",)
    if candidate.from_slot_id == candidate.to_slot_id:
        return ("DISTINCT_TARGET_REQUIRED",)
    if any(key not in slots for key in (candidate.from_slot_id, candidate.to_slot_id)):
        return ("UNKNOWN_SOURCE_SLOT",)
    if any(h.initial_owner_id == candidate.to_slot_id for h in stock.original_stock):
        return ("TARGET_OCCUPIED",)
    if hu.archetype_id not in {"SMALL_CARTON", "STANDARD_CARTON"}:
        return ("UNSUPPORTED_MANUAL_ARCHETYPE",)
    if hu.gross_mass_kg > min(F(15), candidate.actor.max_gross_kg):
        return ("MANUAL_ACTOR_MASS_LIMIT",)
    if not all(_ground(slots[key]) for key in (candidate.from_slot_id, candidate.to_slot_id)):
        return ("MANUAL_L1_ACCESS_REQUIRED",)
    policy = document(bundle, "port-resource-policy-v3.json")
    shippers = next(p["actor_ids"] for p in policy["pools"] if p["pool_id"] == "SHIPPERS_SHARED")
    if (
        candidate.actor.actor_id not in shippers
        or candidate.actor.actor_id not in choices.permitted_actor_ids
    ):
        return ("EXPLICIT_EXISTING_ACTOR_PERMISSION_REQUIRED",)
    catalog = SourceAdmissionCatalog.from_bundle(bundle)
    capability = SelectedCapability(
        Handler(
            "manual_operator",
            ("SMALL_CARTON", "STANDARD_CARTON"),
            Decimal(15),
            Decimal(str(storage["manual_access"]["max_grasp_height_m"])),
        ),
        "manual_hand_carry",
        frozenset(),
    )
    reasons = tuple(
        reason
        for key in (candidate.from_slot_id, candidate.to_slot_id)
        for reason in catalog.evaluate(
            hu.hu_id, key, capability, placements=catalog.baseline
        ).reasons
    )
    return tuple(dict.fromkeys(reasons))


def reservation_reasons(
    bundle: V3Bundle,
    stock: PlacementInventory,
    choices: PlacementChoices,
    candidate: PlacementCandidate,
    hu: StockHU,
) -> tuple[str, ...]:
    declared = {(h.receipt_job_id, h.hu_id): h for h in stock.declared_receipts}
    targets = choices.receipt_targets
    keys = [(t.receipt_job_id, t.hu_id) for t in targets]
    if len(set(keys)) != len(keys) or any(k not in declared for k in keys):
        return ("RECEIPT_DECLARATION_MISMATCH",)
    if set(keys) != set(declared):
        return ("MISSING_RECEIPT_PLACEMENT_BINDING",)
    slots = {r["slot_id"]: r for r in document(bundle, "storage-slots-v3.json")["slots"]}
    identities = [t.slot_id for t in targets]
    if any(key not in slots for key in identities) or len(set(identities)) != len(identities):
        return ("INVALID_RECEIPT_SLOT_RESERVATION",)
    occupied = {h.initial_owner_id for h in stock.original_stock}
    if any(key in occupied for key in identities) or candidate.to_slot_id in identities:
        return ("TARGET_OR_RECEIPT_SLOT_RESERVED",)
    catalog = SourceAdmissionCatalog.from_bundle(bundle)
    for target in targets:
        reasons = _receipt_fit(
            catalog, declared[target.receipt_job_id, target.hu_id], target.slot_id
        )
        if reasons:
            return reasons
    residents = [(h.initial_owner_id, h.gross_mass_kg) for h in stock.original_stock]
    residents += [(t.slot_id, declared[t.receipt_job_id, t.hu_id].gross_mass_kg) for t in targets]
    if slots[candidate.from_slot_id]["module_id"] != slots[candidate.to_slot_id]["module_id"]:
        residents.append((candidate.to_slot_id, hu.gross_mass_kg))
    return _capacity(bundle, slots, residents, candidate)


def receipt_slot_reasons(bundle: V3Bundle, hu: StockHU, slot_id: str) -> tuple[str, ...]:
    """Physical space only; receipt handling and availability remain unproved."""
    return _receipt_fit(SourceAdmissionCatalog.from_bundle(bundle), hu, slot_id)


def _receipt_fit(catalog: SourceAdmissionCatalog, hu: StockHU, slot_id: str) -> tuple[str, ...]:
    cargo, slot = catalog.cargo[hu.archetype_id], catalog.slots[slot_id]
    if cargo.storage_families and slot.storage_family not in cargo.storage_families:
        return ("RECEIPT_STORAGE_FAMILY",)
    if hu.gross_mass_kg > F(slot.slot.max_payload_kg):
        return ("RECEIPT_SLOT_PAYLOAD",)
    # A sole handler failure is returned only after every physical storage check passes.
    result = storage_admission(cargo.cargo, slot.slot, StorageState(), None)
    return () if result.reasons == ("HANDLER_UNAVAILABLE",) else tuple(result.reasons)


def _capacity(
    bundle: V3Bundle,
    slots: dict[str, Any],
    residents: list[tuple[str | None, F]],
    candidate: PlacementCandidate,
) -> tuple[str, ...]:
    count: Counter[str] = Counter()
    mass: dict[str, F] = defaultdict(F)
    for owner, gross in residents:
        if owner is None or owner not in slots:
            return ("UNKNOWN_RESIDENT_SLOT",)
        module = slots[owner]["module_id"]
        count[module] += 1
        mass[module] += gross
    modules = {m["module_id"]: m for m in document(bundle, "storage-slots-v3.json")["modules"]}
    for module in sorted(count):
        if count[module] > modules[module]["max_handling_units"]:
            return ("MODULE_HU_CAPACITY",)
        if mass[module] > F(str(modules[module]["max_module_payload_kg"])):
            return ("MODULE_PAYLOAD",)
    return ()
