"""Fresh canonical C10 stock and outbound cargo rights, independent of predicted volumes."""

from pathlib import Path

from app.v3.adaptation_authority import require_same_authority
from app.v3.input_models import HandlingUnit
from app.v3.inputs import load_v3_bundle
from app.v3.workload_models import WorkloadSource
from app.v3.workload_source import load_workload_source


def fresh_projection_source(
    retained: WorkloadSource,
) -> tuple[WorkloadSource, tuple[HandlingUnit, ...], dict[str, frozenset[str]]]:
    base = Path(__file__).resolve().parents[2] / "data/v3-proposal"
    bundle = load_v3_bundle(base)
    source = load_workload_source(bundle)
    require_same_authority(retained, source)
    ports = {
        port.port_id: frozenset(port.allowed_cargo_archetype_ids)
        for port in bundle.ports
        if port.direction == "outbound"
    }
    return source, bundle.handling_units, ports
