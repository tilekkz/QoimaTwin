"""Source compiler inputs or explicit analytical fixtures, with separate closed admission paths."""

from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import COORDINATOR_VERSION, CoordinatorProfile
from app.v3.coordinator_native_decode import decode, encode
from app.v3.coordinator_units import order_views, preflight_units
from app.v3.coordinator_units_validate import validate_resources
from app.v3.coordinator_validation import validate_horizon, validate_profile
from app.v3.flow_profile_sources import _pinned_reference, _same_types
from app.v3.flow_profile_wire import record
from app.v3.light_flow_models import FlowProfile
from app.v3.stock_ledger import StockLedger
from app.v3.whole_flow_validate import _validate_whole_flow, validate_whole_flow
from app.v3.whole_run_physical import require_conveyor

if TYPE_CHECKING:
    from app.v3.coordinator_profile import CompiledCoordinatorProfile

HAND_VERSION = "qoima-coordinator-hand-inputs-0.1.0"


@dataclass(frozen=True, slots=True)
class HandCoordinatorInputs:
    profile: CoordinatorProfile
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes
    input_hash: str
    registry_common_hash: str


type RunInputs = CompiledCoordinatorProfile | HandCoordinatorInputs


def _preflight(
    profile: CoordinatorProfile, conveyor: ConveyorSource, horizon: int, end: int
) -> None:
    if profile.world.receipts.flow.orders and profile.unit_resources is None:
        raise ValueError("Coordinator namespace3 publication requires explicit unit resources")
    validate_profile(profile)
    validate_resources(profile, conveyor)
    validate_horizon(profile, horizon, end)
    if profile.unit_resources is None:
        validate_whole_flow(profile.world, conveyor)
        return
    views = order_views(profile)

    def units(flow: FlowProfile, source: ConveyorSource, ledger: StockLedger) -> None:
        preflight_units(views, source, ledger)

    _validate_whole_flow(profile.world, conveyor, unit_validator=units, picker_home_at_cart=False)


def freeze_hand_inputs(
    profile: CoordinatorProfile, conveyor: ConveyorSource, horizon_tick: int, end_tick: int
) -> HandCoordinatorInputs:
    if type(profile) is not CoordinatorProfile:
        raise ValueError("Exact coordinator analytical profile required")
    decoded = decode(CoordinatorProfile, encode(profile))
    if not _same_types(profile, decoded):
        raise ValueError("Coordinator analytical profile exact types differ")
    flow = profile.world.receipts.flow
    if flow.source_revision is not None or flow.source_hashes:
        raise ValueError("Analytical coordinator profile cannot impersonate source-bound input")
    require_conveyor(conveyor)
    _preflight(profile, conveyor, horizon_tick, end_tick)
    common = profile.registry.registry_common_hash
    raw = canonical_bytes(
        {
            "compiler_version": HAND_VERSION,
            "engine_version": COORDINATOR_VERSION,
            "scope": "analytical_fixture",
            "profile": encode(profile),
            "conveyor": record(conveyor),
            "registry_common_hash": common,
            "horizon_tick": horizon_tick,
            "end_tick": end_tick,
        }
    )
    return HandCoordinatorInputs(
        profile, horizon_tick, end_tick, raw, sha256(raw).hexdigest(), common
    )


def _load_hand(raw: bytes, value: dict[str, Any]) -> HandCoordinatorInputs:
    keys = {
        "compiler_version",
        "engine_version",
        "scope",
        "profile",
        "conveyor",
        "registry_common_hash",
        "horizon_tick",
        "end_tick",
    }
    if value.keys() != keys or value["scope"] != "analytical_fixture":
        raise ValueError("Analytical coordinator envelope has unknown fields or scope")
    if value["engine_version"] != COORDINATOR_VERSION:
        raise ValueError("Analytical coordinator namespace differs")
    _, conveyor, _ = _pinned_reference()
    profile = decode(CoordinatorProfile, value["profile"])
    result = freeze_hand_inputs(profile, conveyor, value["horizon_tick"], value["end_tick"])
    if result.frozen_bytes != raw:
        raise ValueError("Analytical coordinator bytes or pinned conveyor differ")
    return result


def load_run_inputs(raw: bytes) -> RunInputs:
    if type(raw) is not bytes:
        raise ValueError("Coordinator inputs require exact immutable bytes")
    value = parse_json(raw)
    if type(value) is not dict or canonical_bytes(value) != raw:
        raise ValueError("Coordinator inputs require canonical object bytes")
    if value.get("compiler_version") == HAND_VERSION:
        return _load_hand(raw, value)
    from app.v3.coordinator_profile import load_coordinator_inputs

    return load_coordinator_inputs(raw)


def verify_inputs(inputs: RunInputs) -> CoordinatorProfile:
    if type(inputs) is not HandCoordinatorInputs:
        from app.v3.coordinator_profile import CompiledCoordinatorProfile

        if type(inputs) is not CompiledCoordinatorProfile:
            raise ValueError("Exact source or analytical coordinator input type required")
    expected = load_run_inputs(inputs.frozen_bytes)
    if not _same_types(inputs, expected):
        raise ValueError("Coordinator retained input exact type differs")
    fields = ("horizon_tick", "end_tick", "input_hash", "registry_common_hash")
    if any(getattr(inputs, key) != getattr(expected, key) for key in fields):
        raise ValueError("Coordinator retained input identity or clock differs")
    if canonical_bytes(encode(inputs.profile)) != canonical_bytes(encode(expected.profile)):
        raise ValueError("Coordinator retained physical profile differs from frozen input")
    return expected.profile
