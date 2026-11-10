"""C04: pinned L09 StorageSlot projection, not inventory or an admission solver."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "docs/v3/contract-proposals"
SCHEMA = BASE / "storage-slot-v3.schema.json"
OUTPUT = BASE / "storage-slots-v3.json"
EVIDENCE = ROOT / "docs/adaptive-v3/evidence/C04.json"
PINS = {
    "storage-layout-v3.json": "dca88f92d6537d7ba1b178235cad79255dbba659a8381d211d636070bf282ab2",
    "layout-manifest-v3.json": "f85a4b840e06dc4285df6dbf8f4f39ec32f9fd8d826c18157ff3c27128c620a8",
    "layout-semantic-index-v3.json": "67fd946600405172548220bcac6e2e1c4609d1aa1be370856ba8bccafe39b75a",
    "layout-links-v3.json": "c1fb96d2a72d29d66932ff4de0213b0bf4ebc0abd92102052f6c6ba841942d65",
    "cargo-archetype-v3.schema.json": "46f7d2e384113225fa73ea2dd1b2e0408de91b715231c14d2606c62d0dad1c88",
    "cargo-archetype-v3.example.json": "fe368164ff73d29b7e1bdb3d66bb33278a7b9c37d880f9652237ef128805cc86",
}
SLOT_COUNTS = {"SMALL": 480, "STANDARD": 240, "HEAVY": 24, "LONG": 24, "FLEX": 8}
MODULE_COUNTS = {"SMALL": 48, "STANDARD": 40, "HEAVY": 24, "LONG": 12, "FLEX": 8}
POLICY = {
    "fit_budget": "HU outer dimensions + 2*c <= usable dimensions on every local axis",
    "x_placement": "centred, clearance at least c on each face",
    "z_placement": "front aligned, front clearance c; remaining rear clearance at least c",
    "y_placement": "HU bottom at bin_anchor.Y; entire 2*c budget above HU",
    "bottom_gap_m": 0, "vertical_top_clearance_factor": 2,
    "service_height_role": "cargo_support_plane_not_grip_target",
    "physical_bounds_role": "module collision AABB is broadphase only, never usable volume or a solid cavity",
    "module_load_rule": "sum of complete HU gross masses across module slots <= module max payload",
    "admission": "not_granted; mass, handler, equipment, support, packing, grip and schedule checks remain separate",
}
ORIENTATION = {"slot_orientation_id": "upright_xyz_in_module", "cargo_orientation_id": "upright_xyz",
               "HU_local_axes_in_module": ["+X", "+Y", "+Z"],
               "module_world_yaw_applied_separately": True, "additional_rotation_permission": False}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def fingerprint(path):
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def checked_bytes(data, expected, label):
    require(hashlib.sha256(data).hexdigest() == expected, "SOURCE_HASH_MISMATCH: " + label)
    return json.loads(data)


def finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "NONFINITE_NUMBER")
    elif isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)


def context():
    inputs = {name: checked_bytes((BASE / name).read_bytes(), digest, name) for name, digest in PINS.items()}
    source = inputs["storage-layout-v3.json"]
    manifest = inputs["layout-manifest-v3.json"]
    example = inputs["cargo-archetype-v3.example.json"]
    binding = example["layout_binding"]
    require(binding == {"manifest_path": "docs/v3/contract-proposals/layout-manifest-v3.json",
                       "manifest_sha256": PINS["layout-manifest-v3.json"],
                       "layout_version": manifest["layout_version"],
                       "layout_content_hash": manifest["layout_content_hash"],
                       "public_runtime_sha256": manifest["public_runtime"]["sha256"]}, "C01_LAYOUT_BINDING_MISMATCH")
    public = ROOT / manifest["public_runtime"]["path"]
    checked_bytes(public.read_bytes(), binding["public_runtime_sha256"], "L12 public runtime")
    reference = ROOT / example["reference_binding"]["path"]
    checked_bytes(reference.read_bytes(), example["reference_binding"]["sha256"], "C01 R03 target")
    for name in ("storage-layout-v3.json", "layout-semantic-index-v3.json", "layout-links-v3.json"):
        record = next(x for x in manifest["inputs"] if x["path"].endswith("/" + name))
        require(record["sha256"] == PINS[name], "L12_SOURCE_BINDING_MISMATCH")
    require(source["layout_version"] == binding["layout_version"], "LAYOUT_VERSION_MISMATCH")
    index = inputs["layout-semantic-index-v3.json"]
    definitions = {(x["kind"], x["id"]) for x in index["definitions"]}
    require(len(definitions) == len(index["definitions"]), "DUPLICATE_TYPED_SOURCE_ID")
    links = inputs["layout-links-v3.json"]
    result = {"source": source, "binding": binding, "definitions": definitions,
              "modules": {x["module_id"]: x for x in source["modules"]},
              "slots": {x["slot_id"]: x for x in source["slots"]},
              "slot_indices": {x["slot_id"]: i for i, x in enumerate(source["slots"])},
              "walk_nodes": {x["node_id"] for x in links["walk_graph"]["nodes"]},
              "vehicle_nodes": {x["node_id"] for x in links["vehicle_graph"]["nodes"]},
              "walk_paths": set(links["walk_graph"]["source_path_arc_map"]),
              "vehicle_paths": set(links["vehicle_graph"]["source_path_arc_map"]),
              "cargo_ids": inputs["cargo-archetype-v3.schema.json"]["properties"]["archetype_id"]["enum"],
              "bindings": [fingerprint(BASE / name) for name in sorted(PINS)] + [fingerprint(public), fingerprint(reference)]}
    require(len(result["modules"]) == 132 and len(result["slots"]) == 776, "SOURCE_ID_COUNT")
    return result


def rotate(point, origin, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return [origin[0] + c * point[0] + s * point[2], origin[1] + point[1],
            origin[2] - s * point[0] + c * point[2]]


def inverse(point, origin, yaw):
    d = [point[i] - origin[i] for i in range(3)]
    c, s = math.cos(yaw), math.sin(yaw)
    return [round(c * d[0] - s * d[2], 12), round(d[1], 12), round(s * d[0] + c * d[2], 12)]


def transformed_bounds(bounds, origin, yaw):
    points = [rotate([x, y, z], origin, yaw) for x in (bounds["min"][0], bounds["max"][0])
              for y in (bounds["min"][1], bounds["max"][1]) for z in (bounds["min"][2], bounds["max"][2])]
    return {"min": [min(p[k] for p in points) for k in range(3)],
            "max": [max(p[k] for p in points) for k in range(3)]}


def close(a, b, label):
    if isinstance(a, dict):
        require(set(a) == set(b), label)
        for key in a:
            close(a[key], b[key], label)
    elif isinstance(a, list):
        require(len(a) == len(b), label)
        for x, y in zip(a, b):
            close(x, y, label)
    else:
        require(abs(a - b) <= 1e-8, label)


def handlers(slot):
    if slot["reserve_only"]:
        return []
    result = []
    def option(mode, cargo, manual=None):
        equipment = {"manual_hand_carry": [], "manual_cart": ["manual_cart"],
                     "forklift_assisted": ["forklift", "approved_load_support"]}[mode]
        return {"transport_tag": mode, "required_handler_tag": "forklift_operator" if mode == "forklift_assisted" else "manual_operator",
                "required_equipment_tags": equipment, "allowed_cargo_archetype_ids": cargo,
                "manual_gross_mass_limit_kg": manual, "availability_asserted": False,
                "operational_admission": False, "source_handler_rule": slot["required_handler"]}
    if slot["manual_pick_allowed"]:
        result += [option(mode, slot["allowed_cargo_archetype_ids"], 15) for mode in ("manual_hand_carry", "manual_cart")]
    if slot["required_handler"] == "forklift_with_approved_support":
        result.append(option("forklift_assisted", slot["allowed_cargo_archetype_ids"]))
    elif slot["required_handler"] == "manual_up_to_15kg_or_ground_fragile_forklift":
        result.append(option("forklift_assisted", ["FRAGILE_CRATE"]))
    return result


def typed_refs(slot, ctx):
    result = []
    values = [("service_node_id", slot["service_node_id"])] + [
        ("access." + key, value) for key, value in slot["access"].items() if isinstance(value, str)]
    for field, value in values:
        is_path = field.endswith("vehicle_approach_id")
        require(("local_path" if is_path else "local_service", value) in ctx["definitions"], "UNKNOWN_TYPED_REFERENCE: " + value)
        graph = "vehicle" if value in ctx["vehicle_paths" if is_path else "vehicle_nodes"] else "walk"
        require(value in ctx[graph + ("_paths" if is_path else "_nodes")], "MISSING_COMPILED_REFERENCE: " + value)
        result.append({"source_field": field, "kind": "local_path" if is_path else graph + "_node",
                       "graph": graph, "id": value})
    return result


def slot_record(source, ctx):
    record = deepcopy(source)
    module = ctx["modules"][source["module_id"]]
    anchor = inverse(source["bin_anchor"], module["world_pos"], module["yaw_rad"])
    w, h, d = source["usable_dimensions_xyz_m"]
    record.update(record_type="StorageSlot", bin_anchor_module_local=anchor,
                  usable_bounds_module_local={"min": [round(anchor[0] - w / 2, 12), anchor[1], round(anchor[2] - d / 2, 12)],
                                              "max": [round(anchor[0] + w / 2, 12), round(anchor[1] + h, 12), round(anchor[2] + d / 2, 12)]},
                  module_physical_bounds_world_broadphase=deepcopy(module["outer_bounds_world"]),
                  reserve_classification="explicit_reserve_region" if source["zone_id"].startswith("RESERVE_") else
                  "upper_level_reserve" if source["reserve_only"] else "active_geometric_candidate",
                  conditional_handler_options=handlers(source), typed_access_references=typed_refs(source, ctx),
                  source_pointer="/slots/" + str(ctx["slot_indices"][source["slot_id"]]))
    return record


def module_record(source, ctx):
    record = deepcopy(source)
    definition = ctx["source"]["module_definitions"][source["family"]]
    record.update(record_type="StorageModule", physical_outer_dimensions_xyz_m=definition["outer"],
                  max_module_payload_kg=definition["module_payload"],
                  max_handling_units=len(definition["levels"]) * len(definition["bays"]),
                  slot_ids=sorted(x["slot_id"] for x in ctx["source"]["slots"] if x["module_id"] == source["module_id"]),
                  region_classification="explicit_reserve_region" if source["zone_id"].startswith("RESERVE_") else "primary_storage_region",
                  collision_bounds_broadphase_only=True)
    return record


def counts(slots, modules):
    return {"slots": len(slots), "modules": len(modules), "slots_by_type": dict(Counter(x["storage_type"] for x in slots)),
            "modules_by_family": dict(Counter(x["family"] for x in modules)),
            "reserve_blocked": sum(x["reserve_only"] and x["retrieval_blocked"] for x in slots),
            "active_geometric_candidates": sum(x["active_pick_candidate"] for x in slots),
            "explicit_reserve_region_slots": sum(x["zone_id"].startswith("RESERVE_") for x in slots),
            "explicit_reserve_region_modules": sum(x["zone_id"].startswith("RESERVE_") for x in modules),
            "upper_primary_region_reserve": sum(x["reserve_only"] and not x["zone_id"].startswith("RESERVE_") for x in slots)}


def project(ctx):
    slots = [slot_record(s, ctx) for s in ctx["source"]["slots"]]
    modules = [module_record(m, ctx) for m in ctx["source"]["modules"]]
    return {"schema_id": "qoima.storage-slots.v3-proposal", "schema_version": "0.1.0", "record_type": "StorageSlotProjection",
            "status": "proposal", "operational_admission": False, "layout_binding": ctx["binding"],
            "source_bindings": ctx["bindings"], "units": {"length": "m", "mass": "kg", "angle": "radian", "up_axis": "Y"},
            "orientation_mapping": ORIENTATION, "placement_policy": POLICY,
            "manual_access": ctx["source"]["manual_access"], "reserve_policy": ctx["source"]["reserve_policy"],
            "module_definitions": ctx["source"]["module_definitions"], "modules": modules, "slots": slots,
            "counts": counts(slots, modules), "scope": "Source projection and compatibility prerequisites only; no inventory, resource availability, cargo admission, scheduling, model fit or new rotations."}


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def schema_document(ctx):
    text = {"type": "string", "minLength": 1}
    number = {"type": "number"}
    positive = {"type": "number", "exclusiveMinimum": 0}
    boolean = {"type": "boolean"}
    vec = {"type": "array", "items": number, "minItems": 3, "maxItems": 3}
    size = {**vec, "items": positive}
    bounds = object_schema({"min": vec, "max": vec})
    strings = lambda item=text: {"type": "array", "items": item, "minItems": 1, "uniqueItems": True}
    access = object_schema({k: text for k in ("cart_stop_id", "worker_node_id", "worker")})
    access["properties"].update(cart_transport_requires_gross_mass_at_most_15kg={"const": True}, vehicle=text, vehicle_approach_id=text)
    access["required"].append("cart_transport_requires_gross_mass_at_most_15kg")
    access["dependentRequired"] = {"vehicle": ["vehicle_approach_id"], "vehicle_approach_id": ["vehicle"]}
    option = object_schema({"transport_tag": {"enum": ["manual_hand_carry", "manual_cart", "forklift_assisted"]},
        "required_handler_tag": {"enum": ["manual_operator", "forklift_operator"]},
        "required_equipment_tags": {"type": "array", "uniqueItems": True, "items": {"enum": ["manual_cart", "forklift", "approved_load_support"]}},
        "allowed_cargo_archetype_ids": strings({"enum": ctx["cargo_ids"]}), "manual_gross_mass_limit_kg": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "availability_asserted": {"const": False}, "operational_admission": {"const": False}, "source_handler_rule": text})
    typed = object_schema({"source_field": text, "kind": {"enum": ["walk_node", "vehicle_node", "local_path"]},
                           "graph": {"enum": ["walk", "vehicle"]}, "id": text})
    properties = {k: text for k in ("slot_id", "module_id", "zone_id", "bin_anchor_meaning", "placement_rule", "required_handler",
                                   "service_node_id", "cargo_mass_packing_and_compatibility_status", "source_pointer")}
    properties.update(record_type={"const": "StorageSlot"}, storage_type={"enum": list(SLOT_COUNTS)},
        level={"type": "integer", "minimum": 1}, bay={"type": "integer", "minimum": 1}, usable_dimensions_xyz_m=size,
        usable_bounds_world=bounds, usable_volume_m3=positive, service_height_m={"type": "number", "minimum": 0},
        bin_anchor=vec, allowed_orientation_ids={"const": ["upright_xyz_in_module"]}, module_world_yaw_rad=number,
        allowed_cargo_archetype_ids=strings({"enum": ctx["cargo_ids"]}), clearance_each_side_m=positive,
        max_payload_kg=positive, max_handling_units={"const": 1}, stacking_allowed={"const": False},
        active_pick_candidate=boolean, reserve_only=boolean, retrieval_blocked=boolean,
        retrieval_block_reason={"type": ["string", "null"]}, manual_gross_mass_limit_kg=positive,
        manual_pick_allowed=boolean, access=access, operational_admission={"const": False},
        bin_anchor_module_local=vec, usable_bounds_module_local=bounds, module_physical_bounds_world_broadphase=bounds,
        reserve_classification={"enum": ["explicit_reserve_region", "upper_level_reserve", "active_geometric_candidate"]},
        conditional_handler_options={"type": "array", "items": option}, typed_access_references={"type": "array", "items": typed, "minItems": 4})
    slot = object_schema(properties)
    mod = object_schema({"module_id": text, "zone_id": text, "family": {"enum": list(MODULE_COUNTS)},
        "world_pos": vec, "yaw_rad": number, "outer_bounds_world": bounds, "operating_bounds_world": bounds,
        "row": {"type": "integer", "minimum": 0}, "aisle": {"type": ["number", "null"]},
        "record_type": {"const": "StorageModule"}, "physical_outer_dimensions_xyz_m": size,
        "max_module_payload_kg": positive, "max_handling_units": {"type": "integer", "minimum": 1}, "slot_ids": strings(),
        "region_classification": {"enum": ["explicit_reserve_region", "primary_storage_region"]},
        "collision_bounds_broadphase_only": {"const": True}})
    document = project(ctx)
    top = {k: {"const": value} for k, value in document.items() if k not in {"slots", "modules"}}
    top.update(slots={"type": "array", "items": {"$ref": "#/$defs/slot"}, "minItems": 776, "maxItems": 776},
               modules={"type": "array", "items": {"$ref": "#/$defs/module"}, "minItems": 132, "maxItems": 132})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:qoima:proposal:storage-slot:v3:0.1.0",
            "title": "Pinned C04 StorageSlot projection; not admission", "$defs": {"slot": slot, "module": mod}, **object_schema(top)}


def validate_slot(record, ctx, structural=True):
    finite(record)
    if structural:
        ctx["slot_validator"].validate(record)
    sid = record["slot_id"]
    require(sid in ctx["slots"], "UNKNOWN_SLOT_ID")
    source = ctx["slots"][sid]
    for key, value in source.items():
        require(record[key] == value, "SOURCE_SLOT_FIELD_MISMATCH: " + key)
    require(record == slot_record(source, ctx), "DERIVED_SLOT_PROJECTION_MISMATCH")
    module = ctx["modules"][record["module_id"]]
    definition = ctx["source"]["module_definitions"][record["storage_type"]]
    require(record["zone_id"] == module["zone_id"] and record["storage_type"] == module["family"], "MODULE_SLOT_KIND_MISMATCH")
    require(("storage_slot", sid) in ctx["definitions"] and ("storage_module", record["module_id"]) in ctx["definitions"] and
            ("zone", record["zone_id"]) in ctx["definitions"], "UNKNOWN_TYPED_STORAGE_REFERENCE")
    require(record["usable_dimensions_xyz_m"] == definition["usable"], "USABLE_NOT_OUTER_DIMENSIONS")
    close(record["usable_volume_m3"], math.prod(definition["usable"]), "BAD_USABLE_VOLUME")
    expected_local = [definition["bays"][record["bay"] - 1], definition["levels"][record["level"] - 1],
                      definition["outer"][2] / 2 - .05 - definition["usable"][2] / 2]
    close(record["bin_anchor_module_local"], expected_local, "LOCAL_ANCHOR_BAY_LEVEL_FRONT_MISMATCH")
    close(record["bin_anchor"], rotate(expected_local, module["world_pos"], module["yaw_rad"]), "ANCHOR_YAW_MISMATCH")
    close(record["usable_bounds_world"], transformed_bounds(record["usable_bounds_module_local"], module["world_pos"], module["yaw_rad"]), "ROTATED_USABLE_BOUNDS_MISMATCH")
    close(record["service_height_m"], record["bin_anchor"][1], "SERVICE_IS_NOT_SUPPORT_PLANE")
    require(record["max_payload_kg"] == definition["payload"] and record["max_handling_units"] == 1, "SLOT_CAPACITY_MISMATCH")
    if record["reserve_only"]:
        require(record["retrieval_blocked"] and not record["active_pick_candidate"] and not record["manual_pick_allowed"] and
                record["retrieval_block_reason"] == "HEIGHT_ACCESS_UNAVAILABLE_PENDING_C08" and not record["conditional_handler_options"], "RESERVE_UNBLOCKED")
    if record["manual_pick_allowed"]:
        require(record["manual_gross_mass_limit_kg"] == 15 and record["service_height_m"] <= 1.25, "MANUAL_CONSTRAINT")
    for option in record["conditional_handler_options"]:
        if option["transport_tag"] == "forklift_assisted" and record["storage_type"] == "STANDARD":
            require(record["level"] == 1 and option["allowed_cargo_archetype_ids"] == ["FRAGILE_CRATE"], "STANDARD_FORKLIFT_RESTRICTION")


def validate_document(document, ctx):
    finite(document)
    require(len(document["slots"]) == len({x["slot_id"] for x in document["slots"]}) == 776, "DUPLICATE_OR_MISSING_SLOT")
    require(len(document["modules"]) == len({x["module_id"] for x in document["modules"]}) == 132, "DUPLICATE_OR_MISSING_MODULE")
    ctx["validator"].validate(document)
    require({x["slot_id"] for x in document["slots"]} == set(ctx["slots"]), "SOURCE_SLOT_IDS_DIFFER")
    require({x["module_id"] for x in document["modules"]} == set(ctx["modules"]), "SOURCE_MODULE_IDS_DIFFER")
    for module in document["modules"]:
        original = ctx["modules"][module["module_id"]]
        require(module == module_record(original, ctx), "MODULE_SOURCE_OR_CAPACITY_MISMATCH")
        w, h, d = module["physical_outer_dimensions_xyz_m"]
        local = {"min": [-w / 2, 0, -d / 2], "max": [w / 2, h, d / 2]}
        close(module["outer_bounds_world"], transformed_bounds(local, module["world_pos"], module["yaw_rad"]), "PHYSICAL_BROADPHASE_BOUNDS_MISMATCH")
        members = [x for x in document["slots"] if x["module_id"] == module["module_id"]]
        require(sum(x["max_payload_kg"] for x in members) == module["max_module_payload_kg"], "MODULE_AGGREGATE_CAPACITY")
        require(len(members) == module["max_handling_units"], "MODULE_HU_CAPACITY")
    for record in document["slots"]:
        validate_slot(record, ctx, structural=False)
    actual = counts(document["slots"], document["modules"])
    require(actual["slots_by_type"] == SLOT_COUNTS and actual["modules_by_family"] == MODULE_COUNTS, "FAMILY_COUNTS")
    require([actual[k] for k in ("reserve_blocked", "active_geometric_candidates", "explicit_reserve_region_slots", "explicit_reserve_region_modules", "upper_primary_region_reserve")] == [188, 588, 48, 8, 140], "RESERVE_COUNTS")
    require(Counter(x["storage_type"] for x in document["slots"] if x["reserve_only"]) == {"STANDARD": 176, "LONG": 12}, "RESERVE_FAMILY_COUNTS")
    return actual


def supported_placement(slot, dimensions):
    """One geometric query only: no cargo identity, assignment or admission."""
    finite(dimensions)
    require(len(dimensions) == 3 and all(type(d) in (int, float) and d > 0 for d in dimensions), "INVALID_HU_DIMENSIONS")
    c = slot["clearance_each_side_m"]
    require(all(Decimal(str(d)) + 2 * Decimal(str(c)) <= Decimal(str(u))
                for d, u in zip(dimensions, slot["usable_dimensions_xyz_m"])), "DIMENSION_CLEARANCE_BUDGET")
    a, bounds = slot["bin_anchor_module_local"], slot["usable_bounds_module_local"]
    return {"centre_local_xyz_m": [a[0], a[1] + dimensions[1] / 2, bounds["max"][2] - c - dimensions[2] / 2],
            "bottom_y_m": a[1], "top_y_m": a[1] + dimensions[1], "support_gap_m": 0,
            "top_headroom_m": bounds["max"][1] - a[1] - dimensions[1], "operational_admission": False}


def negative_cases(document, ctx):
    outcomes = []
    def rejected(name, action):
        try:
            action()
        except (ValueError, ValidationError) as error:
            outcomes.append({"case": name, "rejected": True, "reason": str(error).splitlines()[0]})
        else:
            raise ValueError("INVALID_MUTATION_ACCEPTED: " + name)
    first = document["slots"][0]
    def bad_slot(name, change, sample=first):
        value = deepcopy(sample);change(value);rejected(name, lambda: validate_slot(value, ctx))
    bad_slot("outer_substituted_for_usable", lambda x: x.update(usable_dimensions_xyz_m=[2.4, 1.55, 1]))
    bad_slot("changed_world_yaw", lambda x: x.update(module_world_yaw_rad=0))
    bad_slot("changed_bottom_anchor", lambda x: x["bin_anchor"].__setitem__(1, x["bin_anchor"][1] + .01))
    bad_slot("missing_service_id", lambda x: x.pop("service_node_id"))
    bad_slot("unknown_compiled_node", lambda x: x["access"].update(worker="v3:missing:worker"))
    reserve = next(x for x in document["slots"] if x["reserve_only"])
    bad_slot("reserve_unblocked", lambda x: x.update(retrieval_blocked=False, active_pick_candidate=True), reserve)
    bad_slot("wrong_payload_limit", lambda x: x.update(max_payload_kg=16))
    bad_slot("wrong_HU_capacity", lambda x: x.update(max_handling_units=2))
    bad_slot("hidden_yaw90_permission", lambda x: x.update(allowed_orientation_ids=["yaw90"]))
    bad_slot("wrong_usable_volume", lambda x: x.update(usable_volume_m3=.2))
    bad_slot("nonfinite_dimension", lambda x: x["usable_dimensions_xyz_m"].__setitem__(0, float("nan")))
    bad_slot("negative_dimension", lambda x: x["usable_dimensions_xyz_m"].__setitem__(0, -.1))
    bad_slot("local_anchor_changed_to_cargo_centre", lambda x: x["bin_anchor_module_local"].__setitem__(1, .425))
    bad_slot("local_usable_bounds_changed", lambda x: x["usable_bounds_module_local"]["max"].__setitem__(0, .1))
    bad_slot("reserve_region_misclassified", lambda x: x.update(reserve_classification="active_geometric_candidate"),
             next(x for x in document["slots"] if x["zone_id"].startswith("RESERVE_")))
    standard = next(x for x in document["slots"] if x["storage_type"] == "STANDARD" and not x["reserve_only"])
    bad_slot("standard_carton_forklift_permission", lambda x: x["conditional_handler_options"][-1].update(allowed_cargo_archetype_ids=["STANDARD_CARTON"]), standard)
    bad_slot("handler_availability_claim", lambda x: x["conditional_handler_options"][0].update(availability_asserted=True))
    for name, change in [
        ("duplicate_slot_id", lambda x: x["slots"].__setitem__(1, deepcopy(x["slots"][0]))),
        ("unknown_module_id", lambda x: x["modules"][0].update(module_id="v3:module:missing:001")),
        ("changed_source_binding", lambda x: x["source_bindings"][0].update(sha256="0" * 64)),
        ("changed_module_capacity", lambda x: x["modules"][0].update(max_module_payload_kg=999)),
        ("hovering_support_policy", lambda x: x["placement_policy"].update(bottom_gap_m=.05)),
    ]:
        value = deepcopy(document);change(value);rejected(name, lambda v=value: validate_document(v, ctx))
    rejected("mutated_source_bytes", lambda: checked_bytes((BASE / "storage-layout-v3.json").read_bytes() + b"\n", PINS["storage-layout-v3.json"], "mutated L09"))
    rejected("oversize_HU_dimension_budget", lambda: supported_placement(standard, [1.1, 1.0, .85]))
    rejected("no_extra_vertical_allowance_at_boundary", lambda: supported_placement(standard, [1.1, .95000000001, .85]))
    placement = supported_placement(standard, [1.1, .95, .85])
    close([placement["bottom_y_m"], placement["top_y_m"], placement["top_headroom_m"], placement["support_gap_m"]], [.2, 1.15, .1, 0], "FRAGILE_SUPPORT_CONVENTION")
    return outcomes, placement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    ctx = context();schema = schema_document(ctx);Draft202012Validator.check_schema(schema)
    ctx["validator"] = Draft202012Validator(schema)
    ctx["slot_validator"] = Draft202012Validator({"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/slot"})
    document = project(ctx);actual = validate_document(document, ctx)
    invalid, placement = negative_cases(document, ctx)
    if args.check_only:
        require(SCHEMA.read_bytes() == encoded(schema), "SCHEMA_BYTES_DIFFER")
        require(OUTPUT.read_bytes() == encoded(document), "PROJECTION_BYTES_DIFFER")
    else:
        SCHEMA.write_bytes(encoded(schema));OUTPUT.write_bytes(encoded(document))
        report = {"task_id": "C04", "status": "VERIFY", "owner": "rack_crate",
                  "checked_at_utc": datetime.now(timezone.utc).isoformat(), "counts": actual,
                  "artifacts": [fingerprint(SCHEMA), fingerprint(OUTPUT), fingerprint(Path(__file__))],
                  "source_bindings": ctx["bindings"], "layout_binding": ctx["binding"],
                  "validation": {"schema_2020_12": True, "all_records_source_projection": True,
                                 "typed_compiled_references": True, "world_local_yaw_bounds": True,
                                 "module_capacity_aggregation": True, "reserve_and_conditional_handlers": True},
                  "negative_cases": invalid, "fragile_dimension_query_not_assignment": placement,
                  "independent_projection_check": "pending external direct-source pass",
                  "limits": [document["scope"], POLICY["admission"]], "root_review": "pending; root decides PASS"}
        EVIDENCE.write_bytes(encoded(report))
    print(json.dumps({"task_id": "C04", "mode": "check-only" if args.check_only else "build", "counts": actual,
                      "invalid_mutations_rejected": len(invalid), "schema_sha256": fingerprint(SCHEMA)["sha256"],
                      "projection_sha256": fingerprint(OUTPUT)["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
