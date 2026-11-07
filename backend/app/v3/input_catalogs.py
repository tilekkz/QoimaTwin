"""Catalog, graph, layout and in-scope source-link validation."""

import hashlib
import json
import math
from typing import Any

from .input_checks import close, exact, get_document, indexed, positive, require, rows, schema_check
from .input_json import PREFIX
from .input_pin import LAYOUT_CONTENT_HASH, LAYOUT_VERSION


def validate_catalogs(documents: dict[str, Any]) -> None:
    cargo = get_document(documents, "cargo-catalog-v3.json")
    schema = get_document(documents, "cargo-archetype-v3.schema.json")
    records = rows(cargo, "records", PREFIX + "cargo-catalog-v3.json")
    for i, record in enumerate(records):
        path = f"{PREFIX}cargo-catalog-v3.json/records/{i}"
        schema_check(record, schema, path)
        validate_cargo_arithmetic(record, path)
    indexed(records, "archetype_id", PREFIX + "cargo-catalog-v3.json/records")
    require(len(records) == 8, PREFIX + "cargo-catalog-v3.json/records", "expected 8 archetypes")
    storage = get_document(documents, "storage-slots-v3.json")
    schema_check(
        storage,
        get_document(documents, "storage-slot-v3.schema.json"),
        PREFIX + "storage-slots-v3.json",
    )


def validate_cargo_arithmetic(record: dict[str, Any], path: str) -> None:
    for name in ("unit", "handling_unit"):
        part = record[name]
        close(
            part["bounding_volume_m3"],
            math.prod(part["dimensions_xyz_m"]),
            f"{path}/{name}/bounding_volume_m3",
        )
        contents = "contents_mass_kg" if name == "unit" else "contents_gross_mass_kg"
        require(
            exact(part["gross_mass_kg"])
            == exact(part[contents]) + exact(part["packaging_tare_mass_kg"]),
            f"{path}/{name}/gross_mass_kg",
            "mass arithmetic mismatch",
        )
    hu = record["handling_unit"]
    require(
        exact(hu["contents_gross_mass_kg"])
        == exact(record["unit"]["gross_mass_kg"]) * hu["units_per_handling_unit"],
        f"{path}/handling_unit/contents_gross_mass_kg",
        "mass arithmetic mismatch",
    )


def validate_layout(documents: dict[str, Any]) -> None:
    manifest = get_document(documents, "layout-manifest-v3.json")
    path = PREFIX + "layout-manifest-v3.json"
    require(manifest.get("layout_version") == LAYOUT_VERSION, path, "unsupported layout")
    require(
        manifest.get("layout_content_hash") == LAYOUT_CONTENT_HASH,
        path,
        "unsupported layout content hash",
    )
    require(manifest.get("operational_admission") is False, path, "admission must be false")
    require(manifest.get("scheduling_implemented") is False, path, "scheduling must be false")
    require(manifest.get("data_kind") == "geometry_proposal", path, "expected geometry proposal")
    require(
        manifest["envelope"]["bounds"] == {"min": [0, 0, 0], "max": [144, 8, 72]},
        path + "/envelope/bounds",
        "unsupported envelope",
    )
    envelope = get_document(documents, "layout-v3.envelope.json")
    require(
        envelope.get("bounds") == manifest["envelope"]["bounds"],
        PREFIX + "layout-v3.envelope.json/bounds",
        "envelope binding mismatch",
    )
    validate_zone_links(documents)
    for name, document in documents.items():
        if not name.endswith(".schema.json"):
            validate_bindings(document, name)


def validate_bindings(value: Any, path: str) -> None:
    if isinstance(value, dict):
        if "layout_version" in value:
            require(value["layout_version"] == LAYOUT_VERSION, path, "unsupported layout")
        if "layout_content_hash" in value:
            require(
                value["layout_content_hash"] == LAYOUT_CONTENT_HASH,
                path,
                "layout content hash mismatch",
            )
        if "operational_admission" in value:
            require(value["operational_admission"] is False, path, "admission must be false")
        for key, child in value.items():
            validate_bindings(child, f"{path}/{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            validate_bindings(child, f"{path}/{i}")


def validate_source_links(documents: dict[str, Any], raw_hashes: dict[str, str]) -> None:
    for name, document in documents.items():
        check_source_links(document, raw_hashes, name)


def check_source_links(value: Any, raw_hashes: dict[str, str], path: str) -> None:
    if isinstance(value, dict):
        target = value.get("path")
        if isinstance(target, str) and target in raw_hashes and "sha256" in value:
            require(value["sha256"] == raw_hashes[target], path, f"source hash mismatch: {target}")
        target = value.get("manifest_path")
        if isinstance(target, str) and target in raw_hashes:
            require(
                value.get("manifest_sha256") == raw_hashes[target],
                path,
                "layout manifest source hash mismatch",
            )
        for key, child in value.items():
            check_source_links(child, raw_hashes, f"{path}/{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            check_source_links(child, raw_hashes, f"{path}/{i}")


def validate_graphs(documents: dict[str, Any]) -> dict[str, set[str]]:
    links = get_document(documents, "layout-links-v3.json")
    result: dict[str, set[str]] = {}
    manifest = get_document(documents, "layout-manifest-v3.json")
    for graph, expected in (("walk", (1633, 4000)), ("vehicle", (620, 1316))):
        path = f"{PREFIX}layout-links-v3.json/{graph}_graph"
        data = links[graph + "_graph"]
        nodes = indexed(rows(data, "nodes", path), "node_id", path + "/nodes")
        arcs = indexed(rows(data, "arcs", path), "arc_id", path + "/arcs")
        require((len(nodes), len(arcs)) == expected, path, "compiled node/arc count mismatch")
        for key, arc in arcs.items():
            require(
                arc.get("from_node_id") in nodes and arc.get("to_node_id") in nodes,
                f"{path}/arcs/{key}",
                "unknown graph endpoint",
            )
            positive(arc.get("length_m"), f"{path}/arcs/{key}/length_m")
        ids = sorted(nodes)
        fingerprint = hashlib.sha256(
            (json.dumps(ids, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
        expectation = manifest["id_expectations"][graph + "_node"]
        require(fingerprint == expectation["sorted_ids_sha256"], path, "node identities mismatch")
        result[graph] = set(nodes)
        paths = data.get("source_path_arc_map", {})
        for source_id, arc_ids in paths.items():
            require(
                bool(arc_ids) and set(arc_ids) <= arcs.keys(),
                path,
                f"invalid compiled local path: {source_id}",
            )
        result[graph + "_paths"] = set(paths)
    return result


def validate_zone_links(documents: dict[str, Any]) -> None:
    path = PREFIX + "layout-v3.zones.json"
    zones = indexed(
        rows(get_document(documents, "layout-v3.zones.json"), "zones", path),
        "zone_id",
        path + "/zones",
    )
    require(len(zones) == 40, path, "zone count mismatch")
    for name in ("storage-slots-v3.json",):
        document = get_document(documents, name)
        for key in ("modules", "slots"):
            for i, row in enumerate(rows(document, key, PREFIX + name)):
                require(
                    row.get("zone_id") in zones, f"{PREFIX}{name}/{key}/{i}/zone_id", "unknown zone"
                )
    for direction in ("inbound", "outbound"):
        name = f"ports-v3.{direction}.json"
        for i, port in enumerate(rows(get_document(documents, name), "ports", PREFIX + name)):
            for allocation in port.get("finite_buffer_capacity", {}).get("allocations", []):
                zone_id = allocation.get("zone_id")
                require(zone_id in zones, f"{PREFIX}{name}/ports/{i}", "unknown staging zone")
                require(
                    zones[zone_id].get("kind") == "staging",
                    f"{PREFIX}{name}/ports/{i}",
                    "staging forbidden in referenced zone",
                )
