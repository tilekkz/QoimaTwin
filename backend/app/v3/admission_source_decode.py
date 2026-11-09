"""Project validated pinned source bytes without float arithmetic or added permissions."""

import json
from decimal import Decimal
from typing import Any, cast

from app.v3.admission_models import Cargo, Dimensions, Slot
from app.v3.admission_source_models import HandlingOption, SourceCargo, SourceSlot
from app.v3.input_models import V3Bundle

PREFIX = "docs/v3/contract-proposals/"


def document(bundle: V3Bundle, name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            bundle.documents[PREFIX + name].canonical_bytes,
            parse_float=Decimal,
        ),
    )


def dimensions(values: list[Any]) -> Dimensions:
    x, y, z = values
    return Decimal(x), Decimal(y), Decimal(z)


def handling_option(value: dict[str, Any], archetypes: tuple[str, ...]) -> HandlingOption:
    limit = value.get("manual_gross_mass_limit_kg")
    return HandlingOption(
        value["required_handler_tag"],
        value["transport_tag"],
        frozenset(value["required_equipment_tags"]),
        tuple(value.get("allowed_cargo_archetype_ids", archetypes)),
        None if limit is None else Decimal(limit),
    )


def decode_cargo(value: dict[str, Any]) -> SourceCargo:
    archetype = value["archetype_id"]
    orientation = value["orientation"]
    permitted = orientation["permitted_orientations"]
    mappings = orientation["slot_orientation_mappings"]
    if permitted != [
        {"local_axes_in_destination": ["+X", "+Y", "+Z"], "orientation_id": "upright_xyz"}
    ] or mappings != [
        {"cargo_orientation_id": "upright_xyz", "slot_orientation_id": "upright_xyz_in_module"}
    ]:
        raise ValueError("Unsupported source orientation permission")
    hu = value["handling_unit"]
    return SourceCargo(
        Cargo(
            archetype, dimensions(hu["dimensions_xyz_m"]), Decimal(hu["gross_mass_kg"]), ("xyz",)
        ),
        tuple(value["compatibility"]["storage_type_tags"]),
        tuple(handling_option(mode, (archetype,)) for mode in value["handling"]["modes"]),
    )


def decode_slot(value: dict[str, Any], module: dict[str, Any]) -> SourceSlot:
    if value["allowed_orientation_ids"] != ["upright_xyz_in_module"]:
        raise ValueError("Unsupported source slot orientation permission")
    options = tuple(handling_option(option, ()) for option in value["conditional_handler_options"])
    blocked = (
        value["reserve_only"] or value["retrieval_blocked"] or not value["active_pick_candidate"]
    )
    slot = Slot(
        value["slot_id"],
        value["module_id"],
        dimensions(value["usable_dimensions_xyz_m"]),
        Decimal(value["max_payload_kg"]),
        value["max_handling_units"],
        Decimal(module["max_module_payload_kg"]),
        tuple(value["allowed_cargo_archetype_ids"]),
        ("xyz",),
        Decimal(value["clearance_each_side_m"]),
        Decimal(value["bin_anchor_module_local"][1]),
        Decimal(value["service_height_m"]),
        blocked,
        tuple(sorted({option.handler_tag for option in options})),
    )
    return SourceSlot(
        slot,
        value["storage_type"],
        options,
        value["manual_pick_allowed"],
        Decimal(value["manual_gross_mass_limit_kg"]),
        value["retrieval_blocked"],
        value["retrieval_block_reason"],
    )


def decode_slots(bundle: V3Bundle) -> dict[str, SourceSlot]:
    data = document(bundle, "storage-slots-v3.json")
    modules = {value["module_id"]: value for value in data["modules"]}
    slots = {
        value["slot_id"]: decode_slot(value, modules[value["module_id"]]) for value in data["slots"]
    }
    for module in modules.values():
        capacity = sum(slots[key].slot.max_handling_units for key in module["slot_ids"])
        if capacity > module["max_handling_units"]:
            raise ValueError("Source module HU limit needs an explicit aggregate gate")
    return slots
