"""Closed explicit receipt identity and consistent per-HU/lot definitions."""

from collections.abc import Mapping
from dataclasses import fields

from app.storage.canonical_json import sha256_hex
from app.v3.heavy_inbound_models import BoundHeavyReceipt, HeavyInboundReceipt
from app.v3.workload_models import TimedWorkload, WholeHUTemplate, WorkloadJob
from app.v3.workload_policy import integer
from app.v3.workload_validation import name
from app.v3.workload_wire import template_dict


def validate_additions(values: tuple[HeavyInboundReceipt, ...], horizon: int) -> None:
    if type(values) is not tuple:
        raise ValueError("EXACT_IMMUTABLE_HEAVY_RECEIPTS_REQUIRED")
    if not values:
        raise ValueError("N2_REQUIRES_ACTUAL_HEAVY_INBOUND_INCREASE")
    for row in values:
        if type(row) is not HeavyInboundReceipt:
            raise ValueError("EXACT_HEAVY_RECEIPT_REQUIRED")
        for field in fields(row):
            if field.name != "arrival_tick":
                name(getattr(row, field.name))
        if integer(row.arrival_tick) >= horizon:
            raise ValueError("HEAVY_RECEIPT_ARRIVAL_OUTSIDE_HORIZON")


def _template_key(template: WholeHUTemplate) -> tuple[str, str]:
    return template.sku_id, sha256_hex(template_dict(template))


def _register_lot(lots: dict[str, tuple[str, str]], lot_id: str, key: tuple[str, str]) -> None:
    if lot_id in lots and lots[lot_id] != key:
        raise ValueError("HEAVY_RECEIPT_LOT_DEFINITION_CONFLICT")
    lots[lot_id] = key


def identity_registry(baseline: TimedWorkload) -> tuple[set[str], dict[str, tuple[str, str]]]:
    templates = {t.sku_id: t for t in baseline.source.templates}
    occupied = {hu for t in templates.values() for hu in t.initial_hu_ids}
    lots: dict[str, tuple[str, str]] = {}
    for template in templates.values():
        _register_lot(lots, template.source_lot_id, _template_key(template))
    for job in baseline.jobs:
        occupied.add(job.job_id)
        if job.hu_id is not None:
            occupied.add(job.hu_id)
        if job.lot_id is not None:
            key = _template_key(templates[job.sku_id])
            _register_lot(lots, job.lot_id, key)
    return occupied, lots


def bind_receipt(
    row: HeavyInboundReceipt,
    template: WholeHUTemplate,
    ports: Mapping[str, frozenset[str]],
    occupied: set[str],
    lots: dict[str, tuple[str, str]],
) -> BoundHeavyReceipt:
    if template.archetype_id not in {"HEAVY_BOX", "PALLET_LOAD"}:
        raise ValueError("N2_ADDITION_REQUIRES_HEAVY_OR_PALLET")
    if template.archetype_id not in ports.get(row.port_id, frozenset()):
        raise ValueError("HEAVY_RECEIPT_INLET_NOT_PERMITTED")
    if row.job_id == row.hu_id or {row.job_id, row.hu_id} & (occupied | lots.keys()):
        raise ValueError("HEAVY_RECEIPT_IDENTITY_COLLISION")
    if row.lot_id in occupied or row.lot_id in {row.job_id, row.hu_id}:
        raise ValueError("HEAVY_RECEIPT_IDENTITY_NAMESPACE_COLLISION")
    key = _template_key(template)
    _register_lot(lots, row.lot_id, key)
    occupied.update((row.job_id, row.hu_id))
    offer = WorkloadJob(
        row.job_id,
        "inbound",
        row.sku_id,
        template.archetype_id,
        key[1],
        row.port_id,
        template.quantity_units,
        row.arrival_tick,
        row.hu_id,
        row.lot_id,
    )
    return BoundHeavyReceipt(row, offer, template)
