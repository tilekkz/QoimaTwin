"""Source port, compatible slot and conservative module limits for intact manual HUs."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

from app.v3.input_models import Port, V3Bundle
from app.v3.profile_build import dimensions, document
from app.v3.receipt_flow_models import ReceiptPlace, ReceiptPort
from app.v3.runtime_time import operation_ticks
from app.v3.whole_flow_models import MANUAL_WHOLE_CLASSES, WholeFlowProfile, WholeHUPort


def source_classes(bundle: V3Bundle, profile: WholeFlowProfile) -> dict[str, str]:
    sku = {s.sku_id: s.archetype_id for s in bundle.skus}
    classes = {hu.handling_unit_id: hu.archetype_id for hu in bundle.handling_units}
    for offer in profile.receipts.receipts:
        definition = offer.definition
        if definition.hu_id in classes or sku.get(definition.sku_id) not in MANUAL_WHOLE_CLASSES:
            raise ValueError("Future whole receipt needs a new HU and a known manual source SKU")
        classes[definition.hu_id] = sku[definition.sku_id]
    return classes


def bind_ports(
    bundle: V3Bundle, profile: WholeFlowProfile, classes: dict[str, str]
) -> tuple[tuple[ReceiptPort, ...], tuple[WholeHUPort, ...]]:
    sources = {p.port_id: p for p in bundle.ports}
    receipts = []
    for port in profile.receipts.ports:
        source = sources.get(port.port_id)
        offered = {
            classes[o.definition.hu_id]
            for o in profile.receipts.receipts
            if o.port_id == port.port_id
        }
        if source is None or source.direction != "inbound" or len(offered) != 1:
            raise ValueError("Receipt port needs one explicit offered manual source class")
        seconds = dict(source.seconds_by_archetype).get(next(iter(offered)))
        if seconds is None or len(port.buffer_ids) > source.buffer_capacity:
            raise ValueError("Receipt class or source finite buffer ceiling")
        receipts.append(
            replace(
                port,
                node_id=source.service_node_id,
                service_tick=operation_ticks(F(str(seconds))),
                windows=tuple(
                    (operation_ticks(F(str(a))), operation_ticks(F(str(b))))
                    for a, b in source.open_windows
                ),
            )
        )
    return tuple(receipts), tuple(_outbound(p, sources.get(p.port_id)) for p in profile.ports)


def _outbound(port: WholeHUPort, source: Port | None) -> WholeHUPort:
    if (
        source is None
        or source.direction != "outbound"
        or len(port.buffer_ids) > source.buffer_capacity
    ):
        raise ValueError("Whole outbound port or finite source ceiling")
    services = tuple(
        sorted(
            (key, operation_ticks(F(str(seconds))))
            for key, seconds in source.seconds_by_archetype
            if key in MANUAL_WHOLE_CLASSES
        )
    )
    if not services:
        raise ValueError("Source port has no bounded manual whole-HU service")
    return replace(
        port,
        node_id=source.service_node_id,
        service_ticks=services,
        windows=tuple(
            (operation_ticks(F(str(a))), operation_ticks(F(str(b)))) for a, b in source.open_windows
        ),
    )


def bind_slots(
    bundle: V3Bundle, profile: WholeFlowProfile, classes: dict[str, str]
) -> tuple[tuple[ReceiptPlace, ...], tuple[ReceiptPlace, ...]]:
    rows = {r["slot_id"]: r for r in document(bundle, "storage-slots-v3.json")["slots"]}
    locations = {hu.handling_unit_id: hu.slot_id for hu in bundle.handling_units}
    occupied, future_slots = set(locations.values()), set[str]()
    receipt_places = []
    for offer in profile.receipts.receipts:
        slot = offer.slot_owner_id
        if slot in occupied or slot in future_slots:
            raise ValueError("Receipt target must be a unique initially free source slot")
        future_slots.add(slot)
        locations[offer.definition.hu_id] = slot
        receipt_places.append(_slot(rows, slot, classes[offer.definition.hu_id]))
    whole_places = {}
    for order in profile.orders:
        if order.hu_id not in locations or classes[order.hu_id] not in MANUAL_WHOLE_CLASSES:
            raise ValueError("Whole outbound needs an original or explicitly offered manual HU")
        place = _slot(rows, locations[order.hu_id], classes[order.hu_id])
        whole_places[place.owner_id] = place
    return tuple(receipt_places), tuple(whole_places[key] for key in sorted(whole_places))


def _slot(rows: dict[str, Any], slot_id: str, archetype: str) -> ReceiptPlace:
    if slot_id not in rows:
        raise ValueError("Unknown whole source slot")
    row = rows[slot_id]
    if (
        row["reserve_only"]
        or row["retrieval_blocked"]
        or not row["manual_pick_allowed"]
        or archetype not in row["allowed_cargo_archetype_ids"]
    ):
        raise ValueError("Source slot does not allow active manual whole-HU access")
    return ReceiptPlace(
        slot_id,
        row["service_node_id"],
        dimensions(row["usable_dimensions_xyz_m"]),
        F(str(row["max_payload_kg"])),
        F(str(row["clearance_each_side_m"])),
    )


def check_modules(bundle: V3Bundle, profile: WholeFlowProfile) -> None:
    slots = {s.slot_id: s.module_id for s in bundle.slots}
    sku = {s.sku_id: s.archetype_id for s in bundle.skus}
    mass = {c.archetype_id: F(str(c.gross_mass_kg)) for c in bundle.cargo_archetypes}
    totals: dict[str, F] = {}
    for hu in bundle.handling_units:
        totals[hu.module_id] = totals.get(hu.module_id, F(0)) + F(str(hu.gross_mass_kg))
    for offer in profile.receipts.receipts:
        module = slots[offer.slot_owner_id]
        totals[module] = totals.get(module, F(0)) + mass[sku[offer.definition.sku_id]]
    for row in document(bundle, "storage-slots-v3.json")["modules"]:
        if totals.get(row["module_id"], F(0)) > F(str(row["max_module_payload_kg"])):
            raise ValueError("Baseline plus future intact receipts exceeds source module payload")
