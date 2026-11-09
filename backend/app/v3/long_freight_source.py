"""Fresh pinned C10/C08 authority, never caller graphs, grants or replacement stock."""

from dataclasses import dataclass, fields
from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.input_json import PREFIX
from app.v3.input_models import HandlingUnit, V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.long_freight_models import ORIGINAL_HU, LongFreightAuthority, LongFreightRequest
from app.v3.vehicle_package import load_repository_vehicle_adapter
from app.v3.vehicle_source import VehicleAdapter
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_policy import validate_policy
from app.v3.workload_source import load_workload_source
from app.v3.workload_wire import workload_dict


@dataclass(frozen=True, slots=True)
class LongFreightSource:
    bundle: V3Bundle
    vehicles: VehicleAdapter
    original: HandlingUnit
    authority: LongFreightAuthority


def validate_request(request: LongFreightRequest) -> None:
    if type(request) is not LongFreightRequest:
        raise ValueError("EXACT_LONG_FREIGHT_REQUEST_REQUIRED")
    for field in fields(request):
        value = getattr(request, field.name)
        if type(value) is not str or not value.strip():
            raise ValueError("EXACT_NONEMPTY_LONG_FREIGHT_ID_REQUIRED")


def _original(bundle: V3Bundle, request: LongFreightRequest) -> HandlingUnit:
    if request.hu_id != ORIGINAL_HU:
        raise ValueError("ORIGINAL_LONG_HU_OUT_OF_SCOPE")
    hu = next(hu for hu in bundle.handling_units if hu.handling_unit_id == request.hu_id)
    if hu.archetype_id != "LONG_BUNDLE" or request.source_slot_id != hu.slot_id:
        raise ValueError("ORIGINAL_LONG_SOURCE_MISMATCH")
    if request.target_slot_id not in {s.slot_id for s in bundle.slots}:
        raise ValueError("UNKNOWN_LONG_TARGET_SLOT")
    if request.port_id not in {p.port_id for p in bundle.ports}:
        raise ValueError("UNKNOWN_LONG_PORT")
    return hu


def _raw(base: Path, bundle: V3Bundle, name: str) -> bytes:
    path = PREFIX + name
    expected = next(e.raw_sha256 for e in bundle.source_inventory if e.path == path)
    raw = (base / path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError("LONG_RAW_SOURCE_CHANGED_AFTER_VERIFICATION")
    return raw


def load_source(request: LongFreightRequest, policy: WorkloadPolicy) -> LongFreightSource:
    validate_request(request)
    validate_policy(policy)
    data = Path(__file__).resolve().parents[2] / "data"
    base = data / "v3-proposal"
    bundle = load_v3_bundle(base)
    vehicles = load_repository_vehicle_adapter(base, data / "v3-vehicle-proposal")
    original = _original(bundle, request)
    workload = materialize_workload(load_workload_source(bundle), policy)
    hashes = {e.path: e.raw_sha256 for e in bundle.source_inventory}
    for name, digest in vehicles.source_hashes:
        if PREFIX + name in hashes and hashes[PREFIX + name] != digest:
            raise ValueError("LONG_SOURCE_PACKAGE_CONFLICT")
        hashes[PREFIX + name] = digest
    authority = LongFreightAuthority(
        bundle.source_revision,
        bundle.layout_content_hash,
        tuple(sorted(hashes.items())),
        _raw(base, bundle, "baseline-input-v3.json"),
        _raw(base, bundle, "baseline-assignment-v3.json"),
        bundle.handling_units,
        workload,
        canonical_bytes(workload_dict(workload)),
    )
    return LongFreightSource(bundle, vehicles, original, authority)
