"""Versioned explicit clocks wrap, without rewriting, the original physical input artifact."""

from dataclasses import dataclass
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.interface import Json
from app.v3.receipt_run_types import require_types
from app.v3.stock_ledger import StockLedger
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_profile_source import BoundWholeSource
from app.v3.whole_run_physical import (
    hand_record,
    physical_record,
    require_conveyor,
    verify_physical,
)

INPUTS_VERSION = "qoima-whole-publication-inputs-0.1.0"


@dataclass(frozen=True, slots=True)
class WholeRunInputs:
    profile: WholeFlowProfile
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes
    input_hash: str
    physical_input_hash: str


def _clocks(horizon: int, end: int) -> None:
    if type(horizon) is not int or type(end) is not int or not 0 < horizon <= end:
        raise ValueError("Whole clock requires exact positive H and end >= H")


def _wrap(raw: bytes, horizon: int, end: int) -> WholeRunInputs:
    _clocks(horizon, end)
    profile = verify_physical(raw)
    if any(o.arrival_tick >= horizon for o in profile.orders):
        raise ValueError("Whole offered job clock must be within [0,H)")
    physical_hash = sha256(raw).hexdigest()
    frozen = canonical_bytes(
        {
            "inputs_version": INPUTS_VERSION,
            "horizon_tick": horizon,
            "end_tick": end,
            "physical_input_hash": physical_hash,
            "physical_inputs": parse_json(raw),
        }
    )
    return WholeRunInputs(profile, horizon, end, frozen, sha256(frozen).hexdigest(), physical_hash)


def freeze_whole_source(bound: BoundWholeSource, horizon: int, end: int) -> WholeRunInputs:
    if type(bound) is not BoundWholeSource or type(bound.frozen_bytes) is not bytes:
        raise ValueError("Exact typed source whole binding required")
    result = _wrap(bound.frozen_bytes, horizon, end)
    if bound.input_hash != result.physical_input_hash:
        raise ValueError("Original source whole input hash differs")
    _profile_matches(bound.profile, parse_json(bound.frozen_bytes))
    value = parse_json(bound.frozen_bytes)
    if bound.graph_document != canonical_bytes(value["graph_document"]):
        raise ValueError("Original source graph bytes differ")
    return result


def freeze_hand_inputs(
    profile: WholeFlowProfile, conveyor: ConveyorSource, horizon: int, end: int
) -> WholeRunInputs:
    _clocks(horizon, end)
    require_types(profile, WholeFlowProfile)
    require_conveyor(conveyor)
    return _wrap(canonical_bytes(hand_record(profile)), horizon, end)


def load_whole_inputs(raw: bytes) -> WholeRunInputs:
    if type(raw) is not bytes:
        raise ValueError("Whole input envelope requires exact bytes")
    value = parse_json(raw)
    keys = {"inputs_version", "horizon_tick", "end_tick", "physical_input_hash", "physical_inputs"}
    if type(value) is not dict or value.keys() != keys or value["inputs_version"] != INPUTS_VERSION:
        raise ValueError("Whole input envelope has unknown version or fields")
    result = _wrap(
        canonical_bytes(value["physical_inputs"]), value["horizon_tick"], value["end_tick"]
    )
    if result.frozen_bytes != raw:
        raise ValueError("Whole input envelope hash or canonical bytes differ")
    return result


def _profile_matches(profile: WholeFlowProfile, physical: Json) -> None:
    require_types(profile, WholeFlowProfile)
    flow = profile.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    expected = physical_record(profile, ledger)
    if canonical_bytes(expected) != canonical_bytes({k: physical.get(k) for k in expected}):
        raise ValueError("Whole typed profile differs from frozen physical inputs")


def verify_inputs(inputs: WholeRunInputs) -> Json:
    if type(inputs) is not WholeRunInputs:
        raise ValueError("Exact typed whole input envelope required")
    require_types(inputs.profile, WholeFlowProfile)
    _clocks(inputs.horizon_tick, inputs.end_tick)
    verified = load_whole_inputs(inputs.frozen_bytes)
    if (inputs.input_hash, inputs.physical_input_hash, inputs.horizon_tick, inputs.end_tick) != (
        verified.input_hash,
        verified.physical_input_hash,
        verified.horizon_tick,
        verified.end_tick,
    ):
        raise ValueError("Whole input identity/clock differs from frozen envelope")
    frozen = parse_json(inputs.frozen_bytes)
    _profile_matches(inputs.profile, frozen["physical_inputs"])
    return dict(frozen["physical_inputs"])
