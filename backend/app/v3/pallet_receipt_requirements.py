"""Compose source stock, port, directed route and missing custody proofs without crediting HU."""

import json
from collections.abc import Mapping
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import NoReturn

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_sources import _same_types
from app.v3.flow_profile_wire import record
from app.v3.input_json import PREFIX
from app.v3.pallet_receipt_obligations import receipt_obligations
from app.v3.pallet_receipt_route import candidate_route
from app.v3.pallet_receipt_source import source_request
from app.v3.pallet_receipt_types import (
    PalletReceiptError,
    PalletReceiptRequest,
    PalletReceiptRequirements,
)
from app.v3.stock_ledger import StockLedger
from app.v3.stock_receipts import ReceiptDefinition
from app.v3.stock_source import recipes


def compile_pallet_receipt_requirements(
    base_root: Path,
    vehicle_root: Path,
    request: PalletReceiptRequest,
) -> PalletReceiptRequirements:
    source = source_request(base_root, vehicle_root, request)
    bundle, adapter = source.bundle, source.vehicles
    support = next(s for s in adapter.handling.slots if s.slot_id == request.slot_id)
    if support.vehicle_node_id is None:
        raise PalletReceiptError("TARGET_VEHICLE_POSE_MISSING", request.slot_id)
    route = candidate_route(adapter, source.port.service_node_id, support.vehicle_node_id)
    document = bundle.documents[PREFIX + "cargo-catalog-v3.json"]
    exact = json.loads(document.canonical_bytes, parse_float=Fraction)
    row = next(r for r in exact["records"] if r["archetype_id"] == "PALLET_LOAD")
    unit, wrapper = recipes(row, bundle.source_revision)
    receipt = ReceiptDefinition(
        request.receipt_id, request.hu_id, source.template.sku_id, request.lot_id, wrapper.max_units
    )
    hashes = {e.path: e.raw_sha256 for e in bundle.source_inventory}
    hashes.update((PREFIX + k, v) for k, v in adapter.source_hashes)
    result = PalletReceiptRequirements(
        request,
        receipt,
        source.port,
        route,
        bundle.source_revision,
        tuple(sorted(hashes.items())),
        bundle.baseline.handling_units,
        bundle.baseline.quantity_units,
        wrapper.tare_kg + wrapper.max_units * unit.gross_mass_kg,
        source.actor_ids,
        source.receiver_ids,
        "F01",
        "FL01",
        receipt_obligations(),
        "",
    )
    return replace(result, requirements_hash=sha256(canonical_bytes(record(result))).hexdigest())


def verify_pallet_receipt_requirements(
    base_root: Path,
    vehicle_root: Path,
    value: PalletReceiptRequirements,
) -> None:
    if type(value) is not PalletReceiptRequirements:
        raise PalletReceiptError("TYPED_REQUIREMENTS_REQUIRED", "exact source requirement record")
    expected = compile_pallet_receipt_requirements(base_root, vehicle_root, value.request)
    if not _same_types(value, expected) or canonical_bytes(record(value)) != canonical_bytes(
        record(expected)
    ):
        raise PalletReceiptError(
            "RECEIPT_REQUIREMENTS_CHANGED", "reverified raw sources and exact types differ"
        )


def reject_credit(
    base_root: Path,
    vehicle_root: Path,
    request: PalletReceiptRequest,
    ledger: StockLedger,
    leases: Mapping[str, str],
) -> NoReturn:
    """No partial promise or ledger mutation occurs while the physical chain is incomplete."""
    required = compile_pallet_receipt_requirements(base_root, vehicle_root, request)
    ledger.check_invariants()
    current = ledger.inventory_snapshot()
    if request.hu_id in {c.container_id for c in current.containers}:
        raise PalletReceiptError("RECEIPT_ID_ALREADY_LIVE", request.hu_id)
    if request.receipt_id in {r.receipt_id for r in current.registered_receipts}:
        raise PalletReceiptError("RECEIPT_ID_ALREADY_LIVE", request.receipt_id)
    if any(c.owner_id == request.slot_id for c in current.containers):
        raise PalletReceiptError("TARGET_ALREADY_OCCUPIED", request.slot_id)
    keys = {
        "slot:" + request.slot_id,
        "receipt:place:" + request.slot_id,
        "whole:place:" + request.slot_id,
    }
    if keys.intersection(leases):
        raise PalletReceiptError("TARGET_ALREADY_RESERVED", request.slot_id)
    raise PalletReceiptError(
        "PALLET_RECEIPT_PROOF_CHAIN_INCOMPLETE", ";".join(block.code for block in required.blockers)
    )
