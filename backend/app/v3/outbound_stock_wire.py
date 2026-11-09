"""Canonical allocation metadata with every immutable outbound offer retained."""

from dataclasses import asdict
from typing import Any

from app.storage.canonical_json import parse_json, sha256_hex
from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.outbound_stock_models import ALLOCATION_POLICY, STOCK_VERSION, StockAllocation, StockHU
from app.v3.workload_wire import rational


def stock_dict(hu: StockHU) -> dict[str, Any]:
    result = asdict(hu)
    result["gross_mass_kg"] = rational(hu.gross_mass_kg)
    return result


def allocation_dict(row: StockAllocation) -> dict[str, Any]:
    return {
        "offer": asdict(row.offer),
        "status": row.status,
        "hu": None if row.hu is None else stock_dict(row.hu),
        "reason": row.reason,
        "receipt_arrives_after_offer": row.receipt_arrives_after_offer,
        "operational_admission": False,
    }


def stock_hash(original: tuple[StockHU, ...]) -> str:
    return sha256_hex([stock_dict(hu) for hu in original])


def binding_dict(
    inputs: OutboundShiftInputs,
    original: tuple[StockHU, ...],
    incoming: tuple[StockHU, ...],
    rows: tuple[StockAllocation, ...],
) -> dict[str, Any]:
    return {
        "schema_version": STOCK_VERSION,
        "allocation_policy": ALLOCATION_POLICY,
        "shift_inputs": parse_json(inputs.frozen_bytes),
        "shift_input_hash": inputs.input_hash,
        "original_stock": [stock_dict(hu) for hu in original],
        "declared_receipts": [stock_dict(hu) for hu in incoming],
        "allocations": [allocation_dict(row) for row in rows],
        "source_stock_hash": stock_hash(original),
        "operational_admission": False,
        "full_n1_acceptance": False,
    }
