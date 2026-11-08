"""Verify whole physical inputs against the pinned source or explicit hand-only policy."""

from functools import lru_cache

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.flow_profile_sources import _pinned_reference, _same_types
from app.v3.flow_profile_wire import materialized_record, record
from app.v3.interface import Json
from app.v3.profile_models import BufferChoice
from app.v3.stock_ledger import StockLedger
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_flow_validate import validate_whole_flow
from app.v3.whole_profile_source import bind_whole_source
from app.v3.whole_run_profile import decode_profile

HAND_COMPILER = "qoima-whole-hand-fixture-0.1.0"
HAND_POLICY = "explicit-hand-connected-whole-fixture-v1"


def process_records(profile: WholeFlowProfile) -> Json:
    receipt = profile.receipts
    return {
        "receipt_process": {
            "ports": record(receipt.ports),
            "places": record(receipt.places),
            "offers": record(receipt.receipts),
            "pickup_tick": receipt.pickup_tick,
            "place_tick": receipt.place_tick,
        },
        "whole_process": {
            "ports": record(profile.ports),
            "places": record(profile.places),
            "orders": record(profile.orders),
            "pickup_tick": profile.pickup_tick,
            "place_tick": profile.place_tick,
        },
    }


def physical_record(profile: WholeFlowProfile, ledger: StockLedger) -> Json:
    return {
        **materialized_record(profile.receipts.flow, ledger),
        "initial_inventory": record(ledger.inventory_snapshot()),
        **process_records(profile),
    }


def hand_record(profile: WholeFlowProfile) -> Json:
    _, conveyor, _ = _pinned_reference()
    ledger = validate_whole_flow(profile, conveyor)
    if profile.receipts.flow.source_revision is not None or profile.receipts.flow.source_hashes:
        raise ValueError("Hand policy cannot impersonate source-bound whole execution")
    return {
        "compiler_version": HAND_COMPILER,
        "scope": "explicit_hand_connected_whole_fixture",
        "route_policy": HAND_POLICY,
        "conveyor": record(conveyor),
        **physical_record(profile, ledger),
    }


def verify_physical(raw: bytes) -> WholeFlowProfile:
    _verify_physical_bytes(raw)
    return decode_profile(parse_json(raw))


@lru_cache(maxsize=2)
def _verify_physical_bytes(raw: bytes) -> None:
    value = parse_json(raw)
    if type(value) is not dict or canonical_bytes(value) != raw:
        raise ValueError("Whole physical inputs must be canonical object bytes")
    profile = decode_profile(value)
    if profile.receipts.flow.source_revision is None:
        rebuilt = canonical_bytes(hand_record(profile))
    else:
        bundle, conveyor, _ = _pinned_reference()
        buffers = tuple(BufferChoice.model_validate(b) for b in value["local_connectors"])
        rebuilt = bind_whole_source(bundle, conveyor, profile, buffers).frozen_bytes
    if rebuilt != raw:
        raise ValueError("Whole physical inputs differ from verified source/materialization")


def require_conveyor(conveyor: object) -> None:
    _, reference, _ = _pinned_reference()
    if not _same_types(conveyor, reference) or canonical_bytes(record(conveyor)) != canonical_bytes(
        record(reference)
    ):
        raise ValueError("Whole conveyor differs from exact pinned typed source")
