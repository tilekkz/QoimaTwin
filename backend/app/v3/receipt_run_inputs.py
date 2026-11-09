"""Exact receipt-profile authority; a structural interface is never an integrity proof."""

from hashlib import sha256
from typing import Protocol

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_wire import materialized_record, record
from app.v3.interface import Json
from app.v3.receipt_flow_models import ReceiptFlowProfile
from app.v3.receipt_profile import COMPILER_VERSION, compile_receipt_profile
from app.v3.receipt_profile_permissions import ROUTE_POLICY
from app.v3.receipt_run_types import require_types
from app.v3.stock_ledger import StockLedger

HAND_COMPILER = "qoima-receipt-hand-fixture-0.1.0"
HAND_POLICY = "explicit-hand-receipt-fixture-v1"


class ReceiptRunInputs(Protocol):
    @property
    def profile(self) -> ReceiptFlowProfile: ...

    @property
    def horizon_tick(self) -> int: ...

    @property
    def end_tick(self) -> int: ...

    @property
    def frozen_bytes(self) -> bytes: ...

    @property
    def input_hash(self) -> str: ...


def process_record(profile: ReceiptFlowProfile) -> Json:
    return {
        "ports": record(profile.ports),
        "places": record(profile.places),
        "offers": record(profile.receipts),
        "pickup_tick": profile.pickup_tick,
        "place_tick": profile.place_tick,
        "route_policy": ROUTE_POLICY if profile.flow.source_revision is not None else HAND_POLICY,
    }


def verify_frozen(inputs: ReceiptRunInputs) -> Json:
    raw = inputs.frozen_bytes
    if type(raw) is not bytes or sha256(raw).hexdigest() != inputs.input_hash:
        raise ValueError("Receipt frozen input hash mismatch")
    value = parse_json(raw)
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise ValueError("Receipt inputs require canonical JSON object bytes")
    profile = inputs.profile
    require_types(profile, ReceiptFlowProfile)
    flow = profile.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    expected = {
        **materialized_record(flow, ledger),
        "initial_inventory": record(ledger.inventory_snapshot()),
        "receipt_process": process_record(profile),
    }
    if canonical_bytes({k: value.get(k) for k in expected}) != canonical_bytes(expected):
        raise ValueError("Receipt profile/process differs from exact frozen inputs")
    clocks = {"horizon_tick": inputs.horizon_tick, "end_tick": inputs.end_tick}
    if canonical_bytes({k: value["choices"].get(k) for k in clocks}) != canonical_bytes(clocks):
        raise ValueError("Receipt frozen clocks differ")
    verify_source(value)
    return dict(value)


def verify_source(value: Json) -> None:
    source = value["profile"]["source_revision"] is not None
    compiler = COMPILER_VERSION if source else HAND_COMPILER
    scope = (
        "source_bound_connected_receipt_small_proposal"
        if source
        else "explicit_hand_connected_receipt_small_fixture"
    )
    if value.get("compiler_version") != compiler or value.get("scope") != scope:
        raise ValueError("Receipt compiler/scope identity mismatch")
    if not source:
        if value["receipt_process"]["route_policy"] != HAND_POLICY:
            raise ValueError("Explicit hand fixture policy required")
        return
    from app.v3.flow_profile_sources import _pinned_reference

    bundle, conveyor, _ = _pinned_reference()
    rebuilt = compile_receipt_profile(bundle, conveyor, value["choices"])
    if rebuilt.frozen_bytes != canonical_bytes(value):
        raise ValueError("Receipt inputs differ from independently verified source compilation")


def verify_conveyor(frozen: Json, conveyor: ConveyorSource) -> None:
    from app.v3.flow_profile_sources import _pinned_reference, _same_types

    _, reference, _ = _pinned_reference()
    if not _same_types(conveyor, reference):
        raise ValueError("Receipt conveyor differs from exact pinned runtime types/document bytes")
    expected = frozen.get("conveyor")
    if frozen["profile"]["source_revision"] is None:
        # This named test-only compiler policy uses the immutable pinned conveyor context.
        if frozen["compiler_version"] != HAND_COMPILER:
            raise ValueError("Unknown hand fixture conveyor context")
        expected = record(reference)
    if canonical_bytes(record(conveyor)) != canonical_bytes(expected):
        raise ValueError("Receipt execution conveyor differs from frozen physical inputs")
