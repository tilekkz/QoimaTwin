"""Project verified C10 whole-HU mix without converting its unclocked period to a rate."""

import hashlib
import math
from fractions import Fraction
from typing import Any

from app.storage.canonical_json import sha256_hex
from app.v3.input_models import Port, V3Bundle
from app.v3.input_pin import LAYOUT_CONTENT_HASH, SOURCE_REVISION
from app.v3.workload_allocation import validate_weights
from app.v3.workload_models import DemandWeight, WholeHUTemplate, WorkloadSource
from app.v3.workload_policy import integer
from app.v3.workload_validation import name, validate_workload_source

PREFIX = "docs/v3/contract-proposals/"


def _document(bundle: V3Bundle, filename: str) -> dict[str, Any]:
    document = bundle.documents.get(PREFIX + filename)
    if document is None:
        raise ValueError("Required workload source document is missing")
    value = document.decode()
    if not isinstance(value, dict):
        raise ValueError("Workload source document must be an object")
    return value


def _indexed(rows: object, key: str) -> dict[str, dict[str, Any]]:
    if type(rows) is not list:
        raise ValueError("Source records require arrays")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if type(row) is not dict:
            raise ValueError("Source records require objects")
        identity = name(row.get(key))
        if identity in result:
            raise ValueError("Duplicate source record identity")
        result[identity] = row
    return result


def _decimal(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Source weights and measurements require finite JSON numbers")
    result = Fraction(str(value))
    if result < 0:
        raise ValueError("Source weights and measurements must be nonnegative")
    return result


def _template(
    row: dict[str, Any], cargo: dict[str, Any], recipe: dict[str, Any]
) -> WholeHUTemplate:
    hu = cargo["handling_unit"]
    dimensions = hu["dimensions_xyz_m"]
    ids = row["handling_unit_ids"]
    if type(dimensions) is not list or len(dimensions) != 3 or type(ids) is not list:
        raise ValueError("Malformed whole-HU source recipe")
    units = integer(hu["units_per_handling_unit"], positive=True)
    if integer(row["quantity_units"], positive=True) != units * len(ids):
        raise ValueError("Source initial stock must contain complete unchanged HUs")
    orientations = cargo["orientation"]["permitted_orientations"]
    if [orientation["orientation_id"] for orientation in orientations] != ["upright_xyz"]:
        raise ValueError("Whole-HU workload does not infer new orientation permissions")
    return WholeHUTemplate(
        name(row["sku_id"]),
        name(row["archetype_id"]),
        units,
        (_decimal(dimensions[0]), _decimal(dimensions[1]), _decimal(dimensions[2])),
        _decimal(hu["gross_mass_kg"]),
        "upright_xyz",
        name(row["lot_id"]),
        tuple(sorted(name(identity) for identity in ids)),
        sha256_hex(cargo),
        sha256_hex(recipe),
    )


def _weights(
    rows: list[dict[str, Any]], direction: str, ports: dict[str, Port]
) -> tuple[DemandWeight, ...]:
    result = []
    for row in rows:
        moves = _decimal(row[f"expected_{direction}_HU_moves"])
        mix = row[f"{direction}_port_mix"]
        if type(mix) is not dict or not mix or moves <= 0:
            raise ValueError("Source SKU requires positive moves and a declared port mix")
        shares = [(name(port), _decimal(share)) for port, share in mix.items()]
        if sum((share for _, share in shares), Fraction(0)) != 1:
            raise ValueError("Source port shares must sum to exactly one")
        for port_id, share in shares:
            port = ports.get(port_id)
            if port is None or port.direction != direction:
                raise ValueError("Unknown or wrong-direction source port")
            if row["archetype_id"] not in port.allowed_cargo_archetype_ids:
                raise ValueError("Source port forbids whole-HU class")
            result.append(DemandWeight(row["sku_id"], port_id, moves * share))
    return tuple(sorted(result, key=lambda row: (row.sku_id, row.port_id)))


def load_workload_source(bundle: V3Bundle) -> WorkloadSource:
    """Consume a verified frozen loader bundle; initial placements remain untouched."""
    if (
        bundle.source_revision != SOURCE_REVISION
        or bundle.layout_content_hash != LAYOUT_CONTENT_HASH
    ):
        raise ValueError("Workload source pin/layout differs from reviewed C10")
    baseline = _indexed(_document(bundle, "baseline-input-v3.json")["skus"], "sku_id")
    catalog = _document(bundle, "cargo-catalog-v3.json")
    cargo = _indexed(catalog["records"], "archetype_id")
    recipes = _indexed(catalog["packing_recipes"], "archetype_id")
    if set(baseline) != {sku.sku_id for sku in bundle.skus}:
        raise ValueError("Workload source must preserve every verified SKU")
    if not {row["archetype_id"] for row in baseline.values()} <= cargo.keys() & recipes.keys():
        raise ValueError("Source whole-HU recipe reference is missing")
    templates = tuple(
        _template(row, cargo[row["archetype_id"]], recipes[row["archetype_id"]])
        for _, row in sorted(baseline.items())
    )
    if {hu for template in templates for hu in template.initial_hu_ids} != {
        hu.handling_unit_id for hu in bundle.handling_units
    }:
        raise ValueError("Workload source must preserve every initial physical HU")
    ports = {port.port_id: port for port in bundle.ports}
    source = WorkloadSource(
        bundle.source_revision,
        bundle.layout_content_hash,
        tuple(sorted((entry.path, entry.raw_sha256) for entry in bundle.source_inventory)),
        tuple(
            sorted(
                (path, hashlib.sha256(doc.canonical_bytes).hexdigest())
                for path, doc in bundle.documents.items()
            )
        ),
        templates,
        _weights(list(baseline.values()), "inbound", ports),
        _weights(list(baseline.values()), "outbound", ports),
    )
    validate_workload_source(source)
    return source


def expected_port_totals(weights: tuple[DemandWeight, ...]) -> tuple[tuple[str, Fraction], ...]:
    validate_weights(weights, 0)
    totals: dict[str, Fraction] = {}
    for row in weights:
        totals[row.port_id] = totals.get(row.port_id, Fraction(0)) + row.weight
    return tuple(sorted(totals.items()))


def minimum_period_multiplier(weights: tuple[DemandWeight, ...]) -> int:
    validate_weights(weights, 0)
    return math.lcm(*(row.weight.denominator for row in weights))
