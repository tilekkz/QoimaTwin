"""Fresh source composition; future receipt metadata never enters the initial StockSeed."""

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from app.v3.input_json import PREFIX
from app.v3.input_models import HandlingUnit, V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.pallet_cycle_types import PLATFORM_ID
from app.v3.pallet_receipt_types import (
    PalletReceiptError,
    PalletReceiptRequest,
    ReceiptPortRequirement,
)
from app.v3.runtime_time import operation_ticks
from app.v3.vehicle_admission import check_handling_prerequisites
from app.v3.vehicle_evidence import HandlingRequest
from app.v3.vehicle_package import load_repository_vehicle_adapter
from app.v3.vehicle_source import VehicleAdapter


@dataclass(frozen=True, slots=True)
class ReceiptSource:
    bundle: V3Bundle
    vehicles: VehicleAdapter
    template: HandlingUnit
    port: ReceiptPortRequirement
    actor_ids: tuple[str, ...]
    receiver_ids: tuple[str, ...]


def source_request(base: Path, supplement: Path, request: PalletReceiptRequest) -> ReceiptSource:
    _request(request)
    bundle = load_v3_bundle(base)
    adapter = load_repository_vehicle_adapter(base, supplement)
    template = _template(bundle, request)
    _target(bundle, adapter, request)
    port = _port(bundle, request)
    if not any(
        max(request.arrival_tick, a) + port.service_tick <= min(b, request.horizon_tick)
        for a, b in port.windows
    ):
        raise PalletReceiptError("INTAKE_WINDOW_CANNOT_FIT", "30s intake cannot finish by H/close")
    policy = bundle.documents[PREFIX + "port-resource-policy-v3.json"].decode()
    receivers = next(p["actor_ids"] for p in policy["pools"] if p["pool_id"] == "RECEIVERS_SHARED")
    if request.receiver_id not in receivers:
        raise PalletReceiptError("UNKNOWN_SHARED_RECEIVER", request.receiver_id)
    if ("INBOUND_FORKLIFT_PAIR", "F01", "FL01") not in adapter.handling.pairs:
        raise PalletReceiptError("SOURCE_PAIR_MISMATCH", "fixed source pair required")
    return ReceiptSource(
        bundle,
        adapter,
        template,
        port,
        tuple(sorted(policy["actor_ids"])),
        tuple(sorted(receivers)),
    )


def _request(value: PalletReceiptRequest) -> None:
    if type(value) is not PalletReceiptRequest:
        raise PalletReceiptError("TYPED_RECEIPT_REQUIRED", "exact request type required")
    text = (
        value.receipt_id,
        value.hu_id,
        value.lot_id,
        value.template_hu_id,
        value.port_id,
        value.slot_id,
        value.receiver_id,
    )
    if any(type(v) is not str or not v.strip() for v in text):
        raise PalletReceiptError("INVALID_RECEIPT_IDENTITY", "exact nonempty identifiers required")
    clocks = value.arrival_tick, value.horizon_tick, value.end_tick
    if (
        any(type(v) is not int for v in clocks)
        or not 0 <= value.arrival_tick < value.horizon_tick <= value.end_tick
    ):
        raise PalletReceiptError("INVALID_RECEIPT_CLOCK", "require exact 0<=arrival<H<=end")


def _template(bundle: V3Bundle, request: PalletReceiptRequest) -> HandlingUnit:
    rows = {hu.handling_unit_id: hu for hu in bundle.handling_units}
    template = rows.get(request.template_hu_id)
    if template is None or template.archetype_id != "PALLET_LOAD":
        raise PalletReceiptError(
            "UNSUPPORTED_RECEIPT_TEMPLATE", "existing C02 PALLET template required"
        )
    if request.hu_id in rows or request.lot_id in {hu.lot_id for hu in rows.values()}:
        raise PalletReceiptError(
            "RECEIPT_ID_COLLISION", "new HU and lot IDs are explicit future identities"
        )
    return template


def _target(bundle: V3Bundle, adapter: VehicleAdapter, request: PalletReceiptRequest) -> None:
    if request.slot_id in {hu.slot_id for hu in bundle.handling_units}:
        raise PalletReceiptError("TARGET_ALREADY_OCCUPIED", request.slot_id)
    if request.slot_id != PLATFORM_ID:
        raise PalletReceiptError(
            "TARGET_LOCAL_PROOF_UNAVAILABLE", "first target is proved HEAVY_E001 only"
        )
    load = next(v for v in adapter.handling.loads if v.cargo_id == "PALLET_LOAD")
    support = next(v for v in adapter.handling.slots if v.slot_id == PLATFORM_ID)
    value = HandlingRequest(
        request.hu_id,
        "PALLET_LOAD",
        "INBOUND_FORKLIFT_PAIR",
        request.port_id,
        request.slot_id,
        "place",
        load.dimensions_m,
        load.hu_mass_kg,
        support.support_y_m - load.support_to_fork_offset_m,
        (),
    )
    if request.port_id not in {"IN_W_BULK", "IN_N_STANDARD"}:
        raise PalletReceiptError("UNSUPPORTED_PALLET_PORT", request.port_id)
    if not check_handling_prerequisites(
        adapter.handling, value, adapter.source_hashes
    ).design_passed:
        raise PalletReceiptError(
            "TARGET_DESIGN_MISMATCH", "exact C04/C08 design prerequisites failed"
        )


def _port(bundle: V3Bundle, request: PalletReceiptRequest) -> ReceiptPortRequirement:
    document = bundle.documents[PREFIX + "ports-v3.inbound.json"].decode()
    row = next(p for p in document["ports"] if p["port_id"] == request.port_id)
    buffer = row["finite_buffer_capacity"]
    return ReceiptPortRequirement(
        request.port_id,
        row["service_node_id"],
        operation_ticks(
            Fraction(str(row["service_time_rule"]["seconds_by_archetype"]["PALLET_LOAD"]))
        ),
        row["service_capacity"]["max_concurrent_jobs"],
        buffer["total"],
        tuple((r["zone_id"], r["max_handling_units"]) for r in buffer["allocations"]),
        tuple((operation_ticks(a), operation_ticks(b)) for a, b in row["open_windows"]),
    )
