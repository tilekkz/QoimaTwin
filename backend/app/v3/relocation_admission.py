"""Derive L1 manual places from verified source; never allocate live resources."""

from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction as F
from typing import Any

from app.v3.admission_models import Handler
from app.v3.admission_source import SelectedCapability, SourceAdmissionCatalog
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.input_models import V3Bundle
from app.v3.profile_build import dimensions, document
from app.v3.relocation_models import RelocationJob, RelocationPlace
from app.v3.stock_validation import require
from app.v3.whole_profile_binding import check_modules


def source_places(
    bundle: V3Bundle, common: CoordinatorProfile, jobs: tuple[RelocationJob, ...]
) -> tuple[RelocationPlace, ...]:
    """Pure admission helper; the public binder independently authenticates both inputs."""
    source = document(bundle, "storage-slots-v3.json")
    slots = {r["slot_id"]: r for r in source["slots"]}
    modules = {r["module_id"]: r for r in source["modules"]}
    if not jobs:
        return tuple(_place(row, modules[row["module_id"]]) for row in source["slots"])
    require(len(jobs) == 1, "Only one source relocation job")
    catalog = SourceAdmissionCatalog.from_bundle(bundle)
    job = jobs[0]
    hus = [hu for hu in bundle.handling_units if hu.handling_unit_id == job.hu_id]
    require(
        len(hus) == 1 and hus[0].slot_id == job.from_slot_id, "Original source HU/address required"
    )
    require(
        hus[0].archetype_id in {"SMALL_CARTON", "STANDARD_CARTON"}, "Manual original HU required"
    )
    selected = SelectedCapability(
        Handler(
            "manual_operator",
            ("SMALL_CARTON", "STANDARD_CARTON"),
            Decimal(15),
            Decimal(str(source["manual_access"]["max_grasp_height_m"])),
        ),
        "manual_hand_carry",
        frozenset(),
    )
    for slot_id in (job.from_slot_id, job.to_slot_id):
        require(slot_id in slots, "Unknown relocation source slot")
        row = slots[slot_id]
        _manual_ground(row)
        admission = catalog.evaluate(job.hu_id, slot_id, selected, placements=catalog.baseline)
        require(admission.eligible, "Relocation source admission: " + ",".join(admission.reasons))
    require(job.from_slot_id != job.to_slot_id, "Distinct relocation source addresses")
    require(
        not any(hu.slot_id == job.to_slot_id for hu in bundle.handling_units),
        "Relocation destination occupied",
    )
    require(
        not any(r.slot_owner_id == job.to_slot_id for r in common.world.receipts.receipts),
        "Relocation destination reserved for receipt",
    )
    _module_capacity(bundle, common, job, slots, modules)
    # Complete module membership is authority for subsequent live capacity checks.
    return tuple(_place(row, modules[row["module_id"]]) for row in source["slots"])


def _manual_ground(row: dict[str, Any]) -> None:
    require(
        type(row["level"]) is int and row["level"] == 1, "Relocation requires ground-accessible L1"
    )
    require(
        row["manual_pick_allowed"] is True
        and row["reserve_only"] is False
        and row["retrieval_blocked"] is False,
        "Relocation requires active manual access",
    )
    require(
        type(row["max_handling_units"]) is int and row["max_handling_units"] == 1,
        "Single-HU relocation slot required",
    )
    worker = row["service_node_id"]
    require(worker == row["access"]["worker_node_id"], "Relocation service/worker anchor mismatch")
    require(
        any(
            ref["id"] == worker and ref["graph"] == "walk" and ref["kind"] == "walk_node"
            for ref in row["typed_access_references"]
        ),
        "Typed pedestrian worker access required",
    )


def _place(row: dict[str, Any], module: dict[str, Any]) -> RelocationPlace:
    return RelocationPlace(
        row["slot_id"],
        row["service_node_id"],
        dimensions(row["usable_dimensions_xyz_m"]),
        F(str(row["max_payload_kg"])),
        F(str(row["clearance_each_side_m"])),
        row["module_id"],
        F(str(module["max_module_payload_kg"])),
        module["max_handling_units"],
    )


def _module_capacity(
    bundle: V3Bundle,
    common: CoordinatorProfile,
    job: RelocationJob,
    slots: dict[str, Any],
    modules: dict[str, Any],
) -> None:
    check_modules(bundle, common.world)
    counts: Counter[str] = Counter(hu.module_id for hu in bundle.handling_units)
    masses: dict[str, F] = defaultdict(F)
    for hu in bundle.handling_units:
        masses[hu.module_id] += F(str(hu.gross_mass_kg))
    classes = {s.sku_id: s.archetype_id for s in bundle.skus}
    cargo_mass = {c.archetype_id: F(str(c.gross_mass_kg)) for c in bundle.cargo_archetypes}
    for receipt in common.world.receipts.receipts:
        module = slots[receipt.slot_owner_id]["module_id"]
        counts[module] += 1
        masses[module] += cargo_mass[classes[receipt.definition.sku_id]]
    source, target = slots[job.from_slot_id]["module_id"], slots[job.to_slot_id]["module_id"]
    moving = next(hu for hu in bundle.handling_units if hu.handling_unit_id == job.hu_id)
    if source != target:
        counts[target] += 1
        masses[target] += F(str(moving.gross_mass_kg))
    for module in (source, target):
        require(
            counts[module] <= modules[module]["max_handling_units"], "Relocation module HU capacity"
        )
        require(
            masses[module] <= F(str(modules[module]["max_module_payload_kg"])),
            "Relocation module payload with promised receipts",
        )
