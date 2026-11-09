"""Small hand-authored V3 source bundle for interface tests, independent of the loader."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex

PREFIX = "docs/v3/contract-proposals/"


@dataclass(frozen=True)
class Document:
    canonical_bytes: bytes

    def decode(self) -> Any:
        return parse_json(self.canonical_bytes)


@dataclass(frozen=True)
class Source:
    path: str
    raw_sha256: str
    bytes: int


@dataclass(frozen=True)
class Bundle:
    documents: Any
    source_inventory: tuple[Source, ...]
    source_revision: str = "a" * 40
    layout_content_hash: str = "b" * 64


def small_bundle() -> Bundle:
    data = _catalogs() | _stock() | _ports()
    documents = {PREFIX + name: Document(canonical_bytes(value)) for name, value in data.items()}
    inventory = tuple(
        Source(path, sha256_hex(document.decode()), len(document.canonical_bytes))
        for path, document in sorted(documents.items())
    )
    return Bundle(MappingProxyType(documents), inventory)


def _catalogs() -> dict[str, Any]:
    return {
        "layout-manifest-v3.json": {
            "layout_version": "qoima-144x72-v3-proposal",
            "layout_content_hash": "b" * 64,
            "envelope": {"bounds": {"min": [0, 0, 0], "max": [144, 8, 72]}},
            "units": {"length": "m", "mass": "kg", "up_axis": "Y", "angle": "radian"},
        },
        "cargo-catalog-v3.json": {
            "records": [
                {
                    "archetype_id": "SMALL_CARTON",
                    "unit": {"gross_mass_kg": 1, "dimensions_xyz_m": [0.1, 0.1, 0.1]},
                    "handling_unit": {
                        "dimensions_xyz_m": [0.4, 0.2, 0.2],
                        "gross_mass_kg": 2.5,
                        "units_per_handling_unit": 2,
                    },
                    "orientation": {
                        "upright_only": True,
                        "permitted_orientations": [{"orientation_id": "upright_xyz"}],
                    },
                }
            ]
        },
        "sku-catalog-v3.json": {"skus": [{"sku_id": "DEMO_001", "archetype_id": "SMALL_CARTON"}]},
    }


def _stock() -> dict[str, Any]:
    slots = [
        {
            "slot_id": f"S{i}",
            "module_id": "M1",
            "storage_type": "SMALL",
            "reserve_only": False,
            "retrieval_blocked": False,
            "bin_anchor": [10.2, 0.5, 20 - i],
            "usable_dimensions_xyz_m": [1, 1, 1],
            "usable_bounds_world": {"min": [10, 0.5, 19.5 - i], "max": [11, 1.5, 20.5 - i]},
            "max_payload_kg": 10,
            "max_handling_units": 1,
        }
        for i in (1, 2)
    ]
    assignments = [
        {
            "handling_unit_id": f"HU{i}",
            "lot_id": "LOT1",
            "sku_id": "DEMO_001",
            "archetype_id": "SMALL_CARTON",
            "quantity_units": 2,
            "slot_id": f"S{i}",
            "module_id": "M1",
            "orientation_id": "upright_xyz",
            "placement": {"centre_local_xyz_m": [i, 0.6, 0.2], "bottom_y_m": 0.5},
        }
        for i in (1, 2)
    ]
    return {
        "storage-slots-v3.json": {
            "slots": slots,
            "modules": [
                {"module_id": "M1", "world_pos": [10, 0, 20], "yaw_rad": 1.5707963267948966}
            ],
        },
        "baseline-assignment-v3.json": {"assignments": assignments},
    }


def _ports() -> dict[str, Any]:
    def port(identifier: str, direction: str, x: int) -> dict[str, Any]:
        return {
            "port_id": identifier,
            "direction": direction,
            "world_pos": [x, 0, 18],
            "service_node_id": "service:" + identifier,
            "service_node_world_pos": [x, 0, 19],
            "allowed_cargo_archetype_ids": ["SMALL_CARTON"],
            "finite_buffer_capacity": {"total": 2},
        }

    return {
        "ports-v3.inbound.json": {"ports": [port("IN", "inbound", 0)]},
        "ports-v3.outbound.json": {"ports": [port("OUT", "outbound", 144)]},
        "port-resource-policy-v3.json": {
            "actor_ids": ["P01", "F01"],
            "pools": [],
            "forklift_pairs": [],
        },
    }
