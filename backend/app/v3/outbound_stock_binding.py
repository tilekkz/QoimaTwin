"""Public source-bound allocation; each read rebuilds its raw-source and stock authority."""

from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.outbound_shift_inputs import load_outbound_shift_inputs, verify_outbound_shift_inputs
from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.outbound_stock_allocation import allocate_offers, declared_receipts
from app.v3.outbound_stock_models import ALLOCATION_POLICY, STOCK_VERSION, BoundOutboundStock
from app.v3.outbound_stock_source import original_stock
from app.v3.outbound_stock_wire import binding_dict, stock_hash
from app.v3.workload_policy import fields


def _bind_verified(inputs: OutboundShiftInputs) -> BoundOutboundStock:
    original = original_stock(inputs)
    incoming = declared_receipts(inputs.workload)
    rows = allocate_offers(inputs.workload, original, incoming)
    raw = canonical_bytes(binding_dict(inputs, original, incoming, rows))
    return BoundOutboundStock(
        inputs,
        original,
        incoming,
        rows,
        stock_hash(original),
        raw,
        sha256(raw).hexdigest(),
    )


def bind_outbound_stock(inputs: OutboundShiftInputs) -> BoundOutboundStock:
    """Retain all offers, including future dependencies and unallocated shortages."""
    return _bind_verified(verify_outbound_shift_inputs(inputs))


def load_outbound_stock(raw: bytes) -> BoundOutboundStock:
    if type(raw) is not bytes:
        raise ValueError("Outbound stock requires exact immutable bytes")
    value = fields(
        parse_json(raw),
        {
            "schema_version",
            "allocation_policy",
            "shift_inputs",
            "shift_input_hash",
            "original_stock",
            "declared_receipts",
            "allocations",
            "source_stock_hash",
            "operational_admission",
            "full_n1_acceptance",
        },
    )
    if canonical_bytes(value) != raw:
        raise ValueError("Outbound stock requires canonical object bytes")
    if value["schema_version"] != STOCK_VERSION or value["allocation_policy"] != ALLOCATION_POLICY:
        raise ValueError("Unsupported outbound stock version or policy")
    inputs = load_outbound_shift_inputs(canonical_bytes(value["shift_inputs"]))
    expected = _bind_verified(inputs)
    if expected.frozen_bytes != raw:
        raise ValueError("Outbound allocation differs from exact stock, source or offered stream")
    return expected


def verify_outbound_stock(value: BoundOutboundStock) -> BoundOutboundStock:
    if type(value) is not BoundOutboundStock:
        raise ValueError("Exact BoundOutboundStock required")
    expected = load_outbound_stock(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
