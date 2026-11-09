"""Derive future receipt addresses and clocks from unchanged pinned source facts."""

from dataclasses import replace
from fractions import Fraction
from typing import Any

from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_decode import decode_choices
from app.v3.input_models import V3Bundle
from app.v3.light_flow_models import FlowOrder, FlowProfile
from app.v3.light_flow_source import bind_source_profile
from app.v3.profile_build import dimensions
from app.v3.profile_build import document as source_document
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptOffer, ReceiptPlace, ReceiptPort
from app.v3.receipt_profile_geometry import bind_buffers
from app.v3.receipt_profile_permissions import project_manual_cargo
from app.v3.runtime_graph_source import compiled_graph
from app.v3.runtime_time import operation_ticks
from app.v3.stock_receipts import ReceiptDefinition


def _unique(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate receipt {key}")
    return result


def _ports(bundle: V3Bundle, choices: dict[str, Any]) -> tuple[ReceiptPort, ...]:
    ports = {port.port_id: port for port in bundle.ports}
    buffers = _unique(choices["receipt_buffers"], "owner_id")
    rows = _unique(choices["receipt_ports"], "port_id")
    result = []
    used: set[str] = set()
    for key, row in sorted(rows.items()):
        if key not in ports or ports[key].direction != "inbound":
            raise ValueError("Receipt requires a source inbound port")
        port = ports[key]
        service = dict(port.seconds_by_archetype).get("SMALL_CARTON")
        selected = set(row["buffer_owner_ids"])
        if service is None or len(selected) > port.buffer_capacity:
            raise ValueError("Receipt port class or finite buffer ceiling exceeded")
        if any(key_ not in buffers or buffers[key_]["port_id"] != key for key_ in selected):
            raise ValueError("Receipt buffer must belong to its selected source port")
        if used & selected:
            raise ValueError("Receipt buffer is shared by different ports")
        used |= selected
        result.append(
            ReceiptPort(
                key,
                port.service_node_id,
                operation_ticks(Fraction(str(service))),
                tuple(
                    (operation_ticks(Fraction(str(a))), operation_ticks(Fraction(str(b))))
                    for a, b in port.open_windows
                ),
                tuple(sorted(selected)),
                tuple(sorted(row["receiver_ids"])),
            )
        )
    if used != set(buffers):
        raise ValueError("Every declared receipt buffer must have exactly one port")
    return tuple(result)


def _offers(choices: dict[str, Any]) -> tuple[ReceiptOffer, ...]:
    rows = _unique(choices["receipts"], "receipt_id")
    _unique(choices["receipts"], "hu_id")
    _unique(choices["receipts"], "slot_id")
    return tuple(
        ReceiptOffer(
            ReceiptDefinition(
                key, row["hu_id"], row["sku_id"], row["lot_id"], row["quantity_units"]
            ),
            row["arrival_tick"],
            row["port_id"],
            row["slot_id"],
        )
        for key, row in sorted(rows.items())
    )


def _slots(bundle: V3Bundle, offers: tuple[ReceiptOffer, ...]) -> tuple[ReceiptPlace, ...]:
    rows = {
        row["slot_id"]: row for row in source_document(bundle, "storage-slots-v3.json")["slots"]
    }
    occupied = {hu.slot_id for hu in bundle.handling_units}
    result = []
    for offer in offers:
        key = offer.slot_owner_id
        if key not in rows or key in occupied:
            raise ValueError("Receipt requires an initially free source slot")
        row = rows[key]
        if (
            row["reserve_only"]
            or row["retrieval_blocked"]
            or not row["manual_pick_allowed"]
            or "SMALL_CARTON" not in row["allowed_cargo_archetype_ids"]
        ):
            raise ValueError("Receipt slot must permit active manual SMALL storage")
        result.append(
            ReceiptPlace(
                key,
                row["service_node_id"],
                dimensions(row["usable_dimensions_xyz_m"]),
                Fraction(str(row["max_payload_kg"])),
                Fraction(str(row["clearance_each_side_m"])),
            )
        )
    return tuple(sorted(result, key=lambda row: row.owner_id))


def _orders(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    choices: FlowProfile,
    offers: tuple[ReceiptOffer, ...],
) -> tuple[FlowOrder, ...]:
    original = tuple(
        order
        for order in choices.orders
        if order.source_hu not in {offer.definition.hu_id for offer in offers}
    )
    bound = bind_source_profile(bundle, conveyor, replace(choices, orders=original)).orders
    future = {offer.definition.hu_id: offer for offer in offers}
    slots = {
        row["slot_id"]: row for row in source_document(bundle, "storage-slots-v3.json")["slots"]
    }
    result = list(bound)
    for order in choices.orders:
        if order.source_hu not in future:
            continue
        slot = slots[future[order.source_hu].slot_owner_id]
        result.append(
            replace(
                order,
                source_node=slot["service_node_id"],
                cart_source_node=slot["access"]["cart_stop_id"],
            )
        )
    return tuple(sorted(result, key=lambda order: order.order_id))


def _module_capacity(bundle: V3Bundle, offers: tuple[ReceiptOffer, ...]) -> None:
    slots = {row.slot_id: row.module_id for row in bundle.slots}
    sku = {row.sku_id: row.archetype_id for row in bundle.skus}
    cargo = {row.archetype_id: row for row in bundle.cargo_archetypes}
    total: dict[str, Fraction] = {}
    for hu in bundle.handling_units:
        total[hu.module_id] = total.get(hu.module_id, Fraction(0)) + Fraction(str(hu.gross_mass_kg))
    for offer in offers:
        if offer.definition.sku_id not in sku or sku[offer.definition.sku_id] != "SMALL_CARTON":
            raise ValueError("Receipt SKU must select an unchanged source SMALL recipe")
        module = slots[offer.slot_owner_id]
        mass = Fraction(str(cargo[sku[offer.definition.sku_id]].gross_mass_kg))
        total[module] = total.get(module, Fraction(0)) + mass
    for module in source_document(bundle, "storage-slots-v3.json")["modules"]:
        if total.get(module["module_id"], Fraction(0)) > Fraction(
            str(module["max_module_payload_kg"])
        ):
            raise ValueError("Baseline plus all receipts exceeds source module payload")


def bind_receipt_profile(
    bundle: V3Bundle, conveyor: ConveyorSource, document: dict[str, Any]
) -> ReceiptFlowProfile:
    choices = decode_choices(document)
    baseline = bind_source_profile(bundle, conveyor, replace(choices, orders=()))
    offers, ports = _offers(document), _ports(bundle, document)
    places = _slots(bundle, offers)
    _module_capacity(bundle, offers)
    links = source_document(bundle, "layout-links-v3.json")
    project_manual_cargo(links)
    buffers = bind_buffers(bundle, document, links)
    flow = replace(
        baseline,
        graph=compiled_graph(links, "walk"),
        orders=_orders(bundle, conveyor, choices, offers),
    )
    return ReceiptFlowProfile(
        flow,
        ports,
        (*places, *buffers),
        offers,
        document["receipt_times"]["pickup"],
        document["receipt_times"]["place"],
    )
