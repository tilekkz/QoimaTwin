"""Cross-record stock conservation and static slot/module constraints."""

import math
from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any

from .input_checks import (
    close,
    exact,
    get_document,
    indexed,
    positive,
    require,
    rows,
)
from .input_json import PREFIX
from .input_models import BaselineStats


def validate_slots(
    documents: dict[str, Any], cargo: dict[str, Any], nodes: dict[str, set[str]]
) -> dict[str, Any]:
    data = get_document(documents, "storage-slots-v3.json")
    path = PREFIX + "storage-slots-v3.json"
    slots = indexed(data["slots"], "slot_id", path + "/slots")
    modules = indexed(data["modules"], "module_id", path + "/modules")
    require(len(slots) == 776 and len(modules) == 132, path, "slot/module count mismatch")
    listed: list[str] = []
    for module in modules.values():
        listed.extend(module["slot_ids"])
        for slot_id in module["slot_ids"]:
            require(slot_id in slots, path + "/modules", f"unknown slot {slot_id}")
            require(
                slots[slot_id]["module_id"] == module["module_id"],
                path + "/modules",
                f"slot module mismatch: {slot_id}",
            )
    require(len(listed) == len(set(listed)) == len(slots), path, "module slot coverage mismatch")
    for slot_id, slot in slots.items():
        require(slot["module_id"] in modules, f"{path}/slots/{slot_id}", "unknown module")
        require(set(slot["allowed_cargo_archetype_ids"]) <= cargo.keys(), path, "unknown cargo")
        for ref in slot["typed_access_references"]:
            require(
                ref["id"]
                in nodes.get(
                    ref["graph"] + ("_paths" if ref["kind"] == "local_path" else ""), set()
                ),
                f"{path}/slots/{slot_id}/typed_access_references",
                "unknown graph node",
            )
    require(
        dict(Counter(s["storage_type"] for s in slots.values())) == data["counts"]["slots_by_type"],
        path + "/counts/slots_by_type",
        "count mismatch",
    )
    require(
        sum(s["active_pick_candidate"] for s in slots.values()) == 588,
        path,
        "active slot count mismatch",
    )
    require(
        sum(s["reserve_only"] and s["retrieval_blocked"] for s in slots.values()) == 188,
        path,
        "blocked reserve count mismatch",
    )
    return slots


def validate_skus(
    documents: dict[str, Any], cargo: dict[str, Any], ports: dict[str, Any]
) -> dict[str, Any]:
    catalog = get_document(documents, "sku-catalog-v3.json")
    path = PREFIX + "sku-catalog-v3.json"
    skus = indexed(rows(catalog, "skus", path), "sku_id", path + "/skus")
    baseline = get_document(documents, "baseline-input-v3.json")
    path = PREFIX + "baseline-input-v3.json"
    stock = indexed(rows(baseline, "skus", path), "sku_id", path + "/skus")
    validate_sku_templates(catalog, cargo, documents)
    require(
        set(skus) == set(stock) == {f"DEMO_{i:03d}" for i in range(1, 201)},
        path,
        "expected the 200 pinned SKU identities",
    )
    indexed(list(stock.values()), "lot_id", path + "/skus")
    for sku_id, sku in stock.items():
        loc = f"{path}/skus/{sku_id}"
        archetype = sku.get("archetype_id")
        require(archetype in cargo, loc + "/archetype_id", "unknown cargo archetype")
        require(skus[sku_id].get("archetype_id") == archetype, loc, "SKU archetype mismatch")
        positive(sku.get("stock_handling_units"), loc + "/stock_handling_units", integer=True)
        positive(sku.get("quantity_units"), loc + "/quantity_units", integer=True)
        ids = sku.get("handling_unit_ids", [])
        require(
            len(ids) == len(set(ids)) == sku["stock_handling_units"],
            loc,
            "HU identity count mismatch",
        )
        require(
            sku["quantity_units"]
            == len(ids) * cargo[archetype]["handling_unit"]["units_per_handling_unit"],
            loc,
            "quantity conservation mismatch",
        )
        for direction in ("inbound", "outbound"):
            validate_mix(
                sku.get(direction + "_port_mix", {}),
                ports,
                archetype,
                direction,
                loc + "/" + direction + "_port_mix",
            )
    return stock


def validate_mix(
    mix: dict[str, Any], ports: dict[str, Any], cargo: str, direction: str, path: str
) -> None:
    require(isinstance(mix, dict) and bool(mix), path, "expected nonempty port mix")
    for port_id, weight in mix.items():
        require(port_id in ports, path, f"unknown port {port_id}")
        port = ports[port_id]
        require(port["direction"] == direction, path, "port mix direction mismatch")
        require(cargo in port["allowed_cargo_archetype_ids"], path, "port cargo mismatch")
        positive(weight, path + "/" + port_id)
    require(sum(exact(v) for v in mix.values()) == 1, path, "port mix must sum exactly to one")


def validate_assignments(
    documents: dict[str, Any],
    cargo: dict[str, Any],
    skus: dict[str, Any],
    slots: dict[str, Any],
    ports: dict[str, Any],
) -> tuple[list[dict[str, Any]], BaselineStats]:
    data = get_document(documents, "baseline-assignment-v3.json")
    path = PREFIX + "baseline-assignment-v3.json"
    require(data.get("actual_engine_run") is False, path, "actual_engine_run must be false")
    assignments = rows(data, "assignments", path)
    units = indexed(assignments, "handling_unit_id", path + "/assignments")
    occupied = indexed(assignments, "slot_id", path + "/assignments")
    expected_ids = {hu for sku in skus.values() for hu in sku["handling_unit_ids"]}
    require(set(units) == expected_ids and len(units) == 530, path, "HU identity coverage mismatch")
    for i, assignment in enumerate(assignments):
        validate_assignment(assignment, cargo, skus, slots, ports, f"{path}/assignments/{i}")
    for sku_id, sku in skus.items():
        selected = [a for a in assignments if a["sku_id"] == sku_id]
        require(
            {a["handling_unit_id"] for a in selected} == set(sku["handling_unit_ids"]),
            path,
            f"HU ownership mismatch: {sku_id}",
        )
        require(
            sum(a["quantity_units"] for a in selected) == sku["quantity_units"],
            path,
            f"quantity conservation mismatch: {sku_id}",
        )
    validate_module_mass(documents, assignments, cargo)
    stats = derive_stats(assignments, skus, slots, cargo)
    validate_summary(data["summary"], stats, assignments, slots, path + "/summary")
    require(len(occupied) == 530, path, "expected 530 occupied slots")
    return assignments, stats


def validate_assignment(
    assignment: dict[str, Any],
    cargo: dict[str, Any],
    skus: dict[str, Any],
    slots: dict[str, Any],
    ports: dict[str, Any],
    path: str,
) -> None:
    sku_id, slot_id = assignment.get("sku_id", ""), assignment.get("slot_id", "")
    require(sku_id in skus, path + "/sku_id", f"unknown SKU {sku_id}")
    require(slot_id in slots, path + "/slot_id", f"unknown slot {slot_id}")
    sku, slot = skus[sku_id], slots[slot_id]
    require(assignment.get("archetype_id") == sku["archetype_id"], path, "archetype mismatch")
    require(assignment.get("lot_id") == sku["lot_id"], path, "lot mismatch")
    require(assignment.get("module_id") == slot["module_id"], path, "module mismatch")
    require(
        slot["active_pick_candidate"] and not slot["retrieval_blocked"],
        path,
        "assignment uses blocked or inactive slot",
    )
    archetype = cargo[sku["archetype_id"]]
    hu = archetype["handling_unit"]
    positive(assignment.get("quantity_units"), path + "/quantity_units", integer=True)
    require(
        assignment["quantity_units"] == hu["units_per_handling_unit"], path, "HU quantity mismatch"
    )
    require(
        archetype["archetype_id"] in slot["allowed_cargo_archetype_ids"],
        path,
        "slot cargo incompatibility",
    )
    require(
        exact(hu["gross_mass_kg"]) <= exact(slot["max_payload_kg"]), path, "slot payload exceeded"
    )
    validate_static_fit(hu, slot, path)
    validate_permissions(assignment, archetype, slot, path)
    for i, leg in enumerate(assignment.get("planning_legs", [])):
        port_id = leg.get("port_id")
        require(port_id in ports, f"{path}/planning_legs/{i}", "unknown planning port")
        require(leg.get("direction") == ports[port_id]["direction"], path, "leg direction mismatch")
        require(
            archetype["archetype_id"] in ports[port_id]["allowed_cargo_archetype_ids"],
            f"{path}/planning_legs/{i}",
            "planning port cargo mismatch",
        )


def validate_module_mass(
    documents: dict[str, Any], assignments: list[dict[str, Any]], cargo: dict[str, Any]
) -> None:
    data = get_document(documents, "baseline-assignment-v3.json")
    storage = get_document(documents, "storage-slots-v3.json")
    modules = {m["module_id"]: m for m in storage["modules"]}
    masses: dict[str, list[Fraction]] = defaultdict(list)
    for assignment in assignments:
        masses[assignment["module_id"]].append(
            exact(cargo[assignment["archetype_id"]]["handling_unit"]["gross_mass_kg"])
        )
    path = PREFIX + "baseline-assignment-v3.json/module_mass_kg"
    require(set(masses) == set(data["module_mass_kg"]), path, "occupied module coverage mismatch")
    for module_id, values in masses.items():
        mass = sum(values, Fraction())
        close(float(mass), data["module_mass_kg"][module_id], f"{path}/{module_id}")
        require(
            mass <= exact(modules[module_id]["max_module_payload_kg"]),
            path,
            "module payload exceeded",
        )
        require(
            len(values) <= modules[module_id]["max_handling_units"],
            path,
            "module HU capacity exceeded",
        )


def derive_stats(
    assignments: list[dict[str, Any]],
    skus: dict[str, Any],
    slots: dict[str, Any],
    cargo: dict[str, Any],
) -> BaselineStats:
    occupied = {a["slot_id"] for a in assignments}
    active = sum(s["active_pick_candidate"] for s in slots.values())
    return BaselineStats(
        sku_count=len(skus),
        handling_units=len(assignments),
        occupied_slots=len(occupied),
        physical_slots=len(slots),
        active_slots=active,
        blocked_reserve_slots=sum(
            s["reserve_only"] and s["retrieval_blocked"] for s in slots.values()
        ),
        free_active_slots=active - len(occupied),
        free_initial_flex_slots=sum(
            s["storage_type"] == "FLEX" and k not in occupied for k, s in slots.items()
        ),
        quantity_units=sum(a["quantity_units"] for a in assignments),
        gross_mass_kg=math.fsum(
            cargo[a["archetype_id"]]["handling_unit"]["gross_mass_kg"] for a in assignments
        ),
    )


def validate_summary(
    summary: dict[str, Any],
    stats: BaselineStats,
    assignments: list[dict[str, Any]],
    slots: dict[str, Any],
    path: str,
) -> None:
    counts = {
        "SKU_count": stats.sku_count,
        "handling_units": stats.handling_units,
        "occupied_slots": stats.occupied_slots,
        "physical_slots": stats.physical_slots,
        "active_geometric_slots": stats.active_slots,
        "blocked_reserve_slots": stats.blocked_reserve_slots,
        "free_active_slots": stats.free_active_slots,
        "free_initial_FLEX_slots": stats.free_initial_flex_slots,
        "quantity_units": stats.quantity_units,
    }
    for key, value in counts.items():
        require(
            type(summary.get(key)) is int and summary[key] == value,
            f"{path}/{key}",
            f"record-derived count mismatch: expected {value}",
        )
    close(summary["gross_mass_kg"], stats.gross_mass_kg, path + "/gross_mass_kg")
    require(stats.quantity_units == 12256, path, "pinned quantity mismatch")
    close(stats.gross_mass_kg, 9403.85, path + "/gross_mass_kg")
    by_type = Counter(slots[a["slot_id"]]["storage_type"] for a in assignments)
    require(dict(by_type) == summary["occupied_by_storage_type"], path, "occupied types mismatch")


def validate_static_fit(hu: dict[str, Any], slot: dict[str, Any], path: str) -> None:
    for axis, (dimension, usable) in enumerate(
        zip(hu["dimensions_xyz_m"], slot["usable_dimensions_xyz_m"], strict=True)
    ):
        require(
            exact(dimension) + 2 * exact(slot["clearance_each_side_m"]) <= exact(usable),
            f"{path}/slot_fit/{axis}",
            "HU dimensions and clearance exceed usable slot",
        )


def validate_permissions(
    assignment: dict[str, Any], archetype: dict[str, Any], slot: dict[str, Any], path: str
) -> None:
    scale = assignment.get("model_scale_factor")
    require(not isinstance(scale, bool) and scale == 1, path, "scaling forbidden")
    require(
        slot["storage_type"] in archetype["compatibility"]["storage_type_tags"],
        path,
        "cargo storage type forbidden",
    )
    orientation = assignment.get("orientation_id")
    permitted = archetype["orientation"]["permitted_orientations"]
    require(
        any(
            o["orientation_id"] == orientation
            and o["local_axes_in_destination"] == ["+X", "+Y", "+Z"]
            for o in permitted
        ),
        path,
        "unsupported orientation: pinned source requires identity local XYZ",
    )
    require(
        any(
            m["cargo_orientation_id"] == orientation
            and m["slot_orientation_id"] in slot["allowed_orientation_ids"]
            for m in archetype["orientation"]["slot_orientation_mappings"]
        ),
        path,
        "unsupported slot orientation",
    )


def validate_sku_templates(
    catalog: dict[str, Any], cargo: dict[str, Any], documents: dict[str, Any]
) -> None:
    path = PREFIX + "sku-catalog-v3.json"
    require(catalog.get("identity_only_import") is True, path, "identity-only import required")
    records = get_document(documents, "cargo-catalog-v3.json")["records"]
    pointers = {f"/records/{i}": r["archetype_id"] for i, r in enumerate(records)}
    for i, sku in enumerate(catalog["skus"]):
        require(sku.get("archetype_id") in cargo, f"{path}/skus/{i}", "unknown archetype")
        pointer = sku.get("cargo_template_pointer", "")
        require(
            pointer in pointers and pointers[pointer] == sku["archetype_id"],
            f"{path}/skus/{i}/cargo_template_pointer",
            "cargo template pointer mismatch",
        )
        scale = sku.get("model_scale_factor")
        require(not isinstance(scale, bool) and scale == 1, f"{path}/skus/{i}", "scaling forbidden")
