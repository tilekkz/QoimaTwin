"""Fresh C10 catalog, stock and source inlet restrictions; no imported C11 intensity."""

from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.heavy_inbound_models import HeavyInboundAuthority
from app.v3.input_json import PREFIX
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_policy import validate_policy
from app.v3.workload_source import load_workload_source
from app.v3.workload_wire import workload_dict


def _raw(base: Path, bundle: V3Bundle, name: str) -> bytes:
    path = PREFIX + name
    expected = next(e.raw_sha256 for e in bundle.source_inventory if e.path == path)
    raw = (base / path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError("HEAVY_RAW_SOURCE_CHANGED_AFTER_VERIFICATION")
    return raw


def load_baseline(
    policy: WorkloadPolicy,
) -> tuple[HeavyInboundAuthority, dict[str, frozenset[str]]]:
    validate_policy(policy)
    base = Path(__file__).resolve().parents[2] / "data/v3-proposal"
    bundle = load_v3_bundle(base)
    baseline = materialize_workload(load_workload_source(bundle), policy)
    authority = HeavyInboundAuthority(
        bundle.source_revision,
        bundle.layout_content_hash,
        tuple(sorted((e.path, e.raw_sha256) for e in bundle.source_inventory)),
        _raw(base, bundle, "baseline-input-v3.json"),
        _raw(base, bundle, "baseline-assignment-v3.json"),
        bundle.handling_units,
        baseline,
        canonical_bytes(workload_dict(baseline)),
    )
    ports = {
        p.port_id: frozenset(p.allowed_cargo_archetype_ids)
        for p in bundle.ports
        if p.direction == "inbound"
    }
    return authority, ports
