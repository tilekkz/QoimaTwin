"""Freeze source-bound receipt choices before constructing the shared runtime."""

import hashlib
from dataclasses import dataclass
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_sources import verified_records
from app.v3.flow_profile_wire import materialized_record, normalized_choices, record
from app.v3.input_models import V3Bundle
from app.v3.receipt_flow_models import ReceiptFlowProfile
from app.v3.receipt_flow_validate import validate_receipt_flow
from app.v3.receipt_profile_permissions import ROUTE_POLICY
from app.v3.receipt_profile_schema import validate_document
from app.v3.receipt_profile_source import bind_receipt_profile

COMPILER_VERSION = "qoima-receipt-flow-profile-0.1.0"


@dataclass(frozen=True, slots=True)
class CompiledReceiptProfile:
    profile: ReceiptFlowProfile
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes
    input_hash: str


def _choices(document: dict[str, Any]) -> dict[str, Any]:
    value = normalized_choices(document)
    for key, identity in (
        ("receipts", "receipt_id"),
        ("receipt_ports", "port_id"),
        ("receipt_buffers", "owner_id"),
    ):
        value[key].sort(key=lambda row: row[identity])
    for port in value["receipt_ports"]:
        port["receiver_ids"].sort()
        port["buffer_owner_ids"].sort()
    return value


def compile_receipt_profile(
    bundle: V3Bundle, conveyor: ConveyorSource, document: Any
) -> CompiledReceiptProfile:
    validate_document(document)
    horizon, end = document["horizon_tick"], document["end_tick"]
    arrivals = [row["arrival_tick"] for row in (*document["receipts"], *document["orders"])]
    if end < horizon or any(tick >= horizon for tick in arrivals):
        raise ValueError("Require positive H<=end and every offered arrival<H")
    sources = verified_records(bundle, conveyor)
    profile = bind_receipt_profile(bundle, conveyor, document)
    ledger = validate_receipt_flow(profile, conveyor)
    frozen = canonical_bytes(
        {
            "compiler_version": COMPILER_VERSION,
            "scope": "source_bound_connected_receipt_small_proposal",
            "choices": _choices(document),
            **sources,
            **materialized_record(profile.flow, ledger),
            "initial_inventory": record(ledger.inventory_snapshot()),
            "receipt_process": {
                "route_policy": ROUTE_POLICY,
                "ports": record(profile.ports),
                "places": record(profile.places),
                "offers": record(profile.receipts),
                "pickup_tick": profile.pickup_tick,
                "place_tick": profile.place_tick,
            },
        }
    )
    return CompiledReceiptProfile(profile, horizon, end, frozen, hashlib.sha256(frozen).hexdigest())
