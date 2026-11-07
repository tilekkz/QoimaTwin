"""Defensive validation for callers constructing immutable typed source values directly."""

import re
from fractions import Fraction

from app.v3.workload_allocation import validate_weights
from app.v3.workload_models import Hashes, WholeHUTemplate, WorkloadSource
from app.v3.workload_policy import integer


def name(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("Workload identifiers must be nonempty strings")
    return value


def digest(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Workload fingerprints must be lowercase SHA256")
    return value


def fingerprints(values: Hashes) -> None:
    if type(values) is not tuple or not values:
        raise ValueError("Source fingerprints must be a nonempty immutable collection")
    names = []
    for row in values:
        if type(row) is not tuple or len(row) != 2:
            raise ValueError("Fingerprint requires source path and digest")
        names.append(name(row[0]))
        digest(row[1])
    if len(names) != len(set(names)):
        raise ValueError("Duplicate source fingerprint")


def validate_template(template: WholeHUTemplate) -> None:
    if type(template) is not WholeHUTemplate:
        raise ValueError("Typed whole-HU template required")
    for value in (template.sku_id, template.archetype_id, template.source_lot_id):
        name(value)
    if template.orientation_id != "upright_xyz":
        raise ValueError("Only unchanged upright C02 templates are supported")
    integer(template.quantity_units, positive=True)
    if type(template.dimensions_xyz_m) is not tuple or len(template.dimensions_xyz_m) != 3:
        raise ValueError("Whole-HU dimensions must be three immutable exact values")
    if any(
        type(v) is not Fraction or v <= 0
        for v in (*template.dimensions_xyz_m, template.gross_mass_kg)
    ):
        raise ValueError("Whole-HU dimensions and mass require positive exact fractions")
    if type(template.initial_hu_ids) is not tuple or not template.initial_hu_ids:
        raise ValueError("Initial physical HU references must be explicit and immutable")
    for identifier in template.initial_hu_ids:
        name(identifier)
    digest(template.cargo_record_sha256)
    digest(template.packing_recipe_sha256)


def validate_workload_source(source: WorkloadSource) -> None:
    if type(source) is not WorkloadSource:
        raise ValueError("Typed workload source required")
    name(source.source_revision)
    digest(source.layout_content_hash)
    fingerprints(source.raw_fingerprints)
    fingerprints(source.document_fingerprints)
    if {p for p, _ in source.raw_fingerprints} != {p for p, _ in source.document_fingerprints}:
        raise ValueError("Raw and canonical source inventories differ")
    if type(source.templates) is not tuple or not source.templates:
        raise ValueError("Frozen source must retain its whole-HU templates")
    for template in source.templates:
        validate_template(template)
    skus = {t.sku_id for t in source.templates}
    hu_ids = [hu for t in source.templates for hu in t.initial_hu_ids]
    if len(skus) != len(source.templates) or len(hu_ids) != len(set(hu_ids)):
        raise ValueError("Duplicate SKU or initial physical HU identity")
    for weights in (source.inbound_weights, source.outbound_weights):
        validate_weights(weights, 1)
        if {row.sku_id for row in weights} != skus:
            raise ValueError("Demand weights must retain every source SKU exactly by reference")
