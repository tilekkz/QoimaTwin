"""Executable schema builder for the isolated static V3 review artifact."""

from app.v3.interface import Json

TEXT = {"type": "string", "minLength": 1}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
NUMBER = {"type": "number"}
POSITIVE = {"type": "number", "exclusiveMinimum": 0}
COUNT = {"type": "integer", "minimum": 0}
VEC3 = {"type": "array", "items": NUMBER, "minItems": 3, "maxItems": 3}
DIM3 = {"type": "array", "items": POSITIVE, "minItems": 3, "maxItems": 3}


def obj(properties: Json) -> Json:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def array(item: Json) -> Json:
    return {"type": "array", "items": item}


def ref(name: str) -> Json:
    return {"$ref": f"#/$defs/{name}"}


def tagged(name: str, properties: Json) -> Json:
    return obj(
        {
            "schema_id": {"const": f"qoima.{name}.v3-proposal"},
            "schema_version": {"const": "0.1.0"},
            "data_kind": {"const": "static_geometry_proposal"},
            "contract_status": {"const": "proposal"},
            "operational_admission": {"const": False},
            **properties,
        }
    )


def schema() -> Json:
    definitions = _common() | _identities() | _geometry() | _stock()
    definitions["catalog"] = _catalog()
    definitions["initial_state"] = tagged(
        "initial-state",
        {
            "state_id": HASH,
            "layout": ref("layout"),
            "source": ref("source"),
            "handling_units": array(ref("hu")),
            "inventory_by_sku": array(
                obj({"sku_id": TEXT, "quantity_units": {"type": "integer", "minimum": 1}})
            ),
            "totals": ref("totals"),
        },
    )
    definitions["manifest"] = tagged(
        "static-manifest",
        {
            "export_id": HASH,
            "catalog": ref("descriptor"),
            "initial_state": ref("descriptor"),
            "source_documents": array(ref("descriptor")),
        },
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:qoima:static-export:v3-proposal:0.1.0",
        "$defs": definitions,
        **tagged(
            "static-export",
            {"export_id": HASH, "catalog": ref("catalog"), "initial_state": ref("initial_state")},
        ),
    }


def _common() -> Json:
    source_ref = obj({"path": TEXT, "raw_sha256": HASH, "bytes": COUNT, "canonical_sha256": HASH})
    return {
        "source": obj(
            {
                "revision": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                "documents": array(source_ref),
                "interface_version": {"const": "qoima-v3-static-interface-1"},
            }
        ),
        "descriptor": obj({"path": TEXT, "bytes": COUNT, "sha256": HASH}),
        "layout": obj(
            {
                "layout_version": {"const": "qoima-144x72-v3-proposal"},
                "layout_content_hash": HASH,
                "bounds": obj({"min": VEC3, "max": VEC3}),
                "units": {
                    "type": "object",
                    "properties": {
                        "length": {"const": "m"},
                        "mass": {"const": "kg"},
                        "up_axis": {"const": "Y"},
                        "angle": {"const": "radian"},
                    },
                    "required": ["length", "mass", "up_axis", "angle"],
                },
                "model_scale_factor": {"const": 1},
            }
        ),
    }


def _identities() -> Json:
    unit = {"dimensions_xyz_m": DIM3, "gross_mass_kg": POSITIVE}
    return {
        "archetype": obj(
            {
                "archetype_id": TEXT,
                "unit": obj(unit),
                "handling_unit": obj(
                    {**unit, "units_per_handling_unit": {"type": "integer", "minimum": 1}}
                ),
                "upright_only": {"type": "boolean"},
                "permitted_orientation_ids": array(TEXT),
            }
        ),
        "sku": obj({"sku_id": TEXT, "archetype_id": TEXT}),
        "actor": obj({"actor_id": TEXT, "profile_status": {"const": "not_defined"}}),
        "asset": obj(
            {
                "archetype_id": TEXT,
                "model_scale_factor": {"const": 1},
                "binding_status": {"const": "not_bound"},
            }
        ),
        "resources": obj(
            {
                "actor_pools": array(obj({"pool_id": TEXT, "actor_ids": array(TEXT)})),
                "equipment_pairs": array(
                    obj(
                        {
                            "pair_id": TEXT,
                            "actor_id": TEXT,
                            "vehicle_id": TEXT,
                            "eligible_direction": {"enum": ["inbound", "outbound"]},
                        }
                    )
                ),
            }
        ),
    }


def _geometry() -> Json:
    return {
        "module": obj({"module_id": TEXT, "world_pos": VEC3, "yaw_rad": NUMBER}),
        "slot": obj(
            {
                "slot_id": TEXT,
                "module_id": TEXT,
                "storage_type": TEXT,
                "reserve_only": {"type": "boolean"},
                "retrieval_blocked": {"type": "boolean"},
                "bin_anchor": VEC3,
                "usable_dimensions_xyz_m": DIM3,
                "usable_bounds_world": obj({"min": VEC3, "max": VEC3}),
                "max_payload_kg": POSITIVE,
                "max_handling_units": {"type": "integer", "minimum": 1},
            }
        ),
        "port": obj(
            {
                "port_id": TEXT,
                "direction": {"enum": ["inbound", "outbound"]},
                "world_pos": VEC3,
                "service_node_id": TEXT,
                "service_node_world_pos": VEC3,
                "allowed_cargo_archetype_ids": array(TEXT),
                "buffer_hu_limit": COUNT,
            }
        ),
    }


def _stock() -> Json:
    pose = obj(
        {
            "world_pos": VEC3,
            "yaw_rad": NUMBER,
            "origin": {"const": "floor_centre_XZ_Y0"},
            "orientation_id": {"const": "upright_xyz"},
        }
    )
    return {
        "hu": obj(
            {
                "handling_unit_id": TEXT,
                "lot_id": TEXT,
                "sku_id": TEXT,
                "archetype_id": TEXT,
                "quantity_units": {"type": "integer", "minimum": 1},
                "owner": obj({"kind": {"const": "storage_slot"}, "id": TEXT}),
                "pose": pose,
                "dimensions_xyz_m": DIM3,
                "gross_mass_kg": POSITIVE,
                "model_scale_factor": {"const": 1},
            }
        ),
        "totals": obj(
            {
                "handling_units": COUNT,
                "occupied_slots": COUNT,
                "quantity_units": COUNT,
                "gross_mass_kg": {"type": "number", "minimum": 0},
            }
        ),
    }


def _catalog() -> Json:
    from app.v3.interface import CAPABILITIES

    counts = {
        name: COUNT
        for name in ("skus", "archetypes", "slots", "modules", "ports", "actors", "handling_units")
    }
    sections = {
        "cargo_archetypes": "archetype",
        "skus": "sku",
        "storage_modules": "module",
        "storage_slots": "slot",
        "ports": "port",
        "actors": "actor",
        "asset_archetypes": "asset",
    }
    return tagged(
        "catalog",
        {
            "catalog_id": HASH,
            "layout": ref("layout"),
            "source": ref("source"),
            "capabilities": obj({name: {"const": value} for name, value in CAPABILITIES.items()}),
            "counts": obj(counts),
            "resource_policy": ref("resources"),
            **{name: array(ref(definition)) for name, definition in sections.items()},
        },
    )
