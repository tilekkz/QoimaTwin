"""Source-labelled V3 catalogs; no V2 coordinates, stock defaults or engine execution."""

from app.v3.catalog_stock import initial_stock
from app.v3.interface import (
    CAPABILITIES,
    CatalogSource,
    Json,
    document,
    envelope,
    fields,
    identity,
    layout_binding,
    source_binding,
)


def build_catalog(bundle: CatalogSource) -> Json:
    sections = _sections(bundle)
    names = {
        "skus": "skus",
        "archetypes": "cargo_archetypes",
        "slots": "storage_slots",
        "modules": "storage_modules",
        "ports": "ports",
        "actors": "actors",
    }
    counts = {key: len(sections[name]) for key, name in names.items()}
    counts["handling_units"] = len(document(bundle, "baseline-assignment-v3.json")["assignments"])
    return identity(
        {
            **envelope("catalog"),
            "layout": layout_binding(bundle),
            "source": source_binding(bundle),
            "capabilities": dict(CAPABILITIES),
            "counts": counts,
            **sections,
        },
        "catalog_id",
    )


def _sections(bundle: CatalogSource) -> Json:
    storage = document(bundle, "storage-slots-v3.json")
    archetypes = document(bundle, "cargo-catalog-v3.json")["records"]
    skus = document(bundle, "sku-catalog-v3.json")["skus"]
    policy = document(bundle, "port-resource-policy-v3.json")
    ports = _ports(bundle)
    actors = [
        {"actor_id": actor, "profile_status": "not_defined"}
        for actor in sorted(policy["actor_ids"])
    ]
    slots = [
        fields(
            row,
            "slot_id module_id storage_type reserve_only retrieval_blocked "
            "bin_anchor usable_dimensions_xyz_m usable_bounds_world "
            "max_payload_kg max_handling_units",
        )
        for row in storage["slots"]
    ]
    return {
        "cargo_archetypes": [_archetype(row) for row in archetypes],
        "skus": [fields(row, "sku_id archetype_id") for row in skus],
        "storage_modules": [
            fields(row, "module_id world_pos yaw_rad") for row in storage["modules"]
        ],
        "storage_slots": slots,
        "ports": ports,
        "actors": actors,
        "resource_policy": {
            "actor_pools": [fields(row, "pool_id actor_ids") for row in policy["pools"]],
            "equipment_pairs": [
                fields(row, "pair_id actor_id vehicle_id eligible_direction")
                for row in policy["forklift_pairs"]
            ],
        },
        "asset_archetypes": [
            {
                "archetype_id": row["archetype_id"],
                "model_scale_factor": 1,
                "binding_status": "not_bound",
            }
            for row in archetypes
        ],
    }


def build_initial_state(bundle: CatalogSource) -> Json:
    return identity(
        {
            **envelope("initial-state"),
            "layout": layout_binding(bundle),
            "source": source_binding(bundle),
            **initial_stock(bundle),
        },
        "state_id",
    )


def _archetype(row: Json) -> Json:
    return {
        "archetype_id": row["archetype_id"],
        "unit": fields(row["unit"], "dimensions_xyz_m gross_mass_kg"),
        "handling_unit": fields(
            row["handling_unit"], "dimensions_xyz_m gross_mass_kg units_per_handling_unit"
        ),
        "upright_only": row["orientation"]["upright_only"],
        "permitted_orientation_ids": [
            value["orientation_id"] for value in row["orientation"]["permitted_orientations"]
        ],
    }


def _ports(bundle: CatalogSource) -> list[Json]:
    result = []
    for name in ("ports-v3.inbound.json", "ports-v3.outbound.json"):
        for port in document(bundle, name)["ports"]:
            row = fields(
                port,
                "port_id direction world_pos service_node_id service_node_world_pos "
                "allowed_cargo_archetype_ids",
            )
            row["buffer_hu_limit"] = port["finite_buffer_capacity"]["total"]
            result.append(row)
    return result
