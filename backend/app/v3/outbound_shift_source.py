"""Authenticate C10/C11 from pinned bytes before deriving the outbound-only scenario."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import sha256_hex
from app.v3.adaptation_authority import require_same_authority
from app.v3.adaptation_pin import INPUT_PATH, PERIOD_UNIT, PREFIX, SCENARIO_ID
from app.v3.adaptation_source import AdaptationPackage, load_adaptation_package
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.outbound_shift_models import (
    PROJECTION_POLICY,
    SCENARIO_VERSION,
    BaselinePlacement,
    N1Scenario,
    ShiftSourceDocument,
)
from app.v3.outbound_shift_projection import project_rows
from app.v3.outbound_shift_wire import scenario_record
from app.v3.workload_models import WorkloadSource
from app.v3.workload_source import _weights, load_workload_source
from app.v3.workload_validation import validate_workload_source


def source_roots() -> tuple[Path, Path]:
    data = Path(__file__).resolve().parents[2] / "data"
    return data / "v3-proposal", data / "v3-adaptation-proposal"


def _raw_source(
    root: Path,
    key: str,
    path: str,
    expected: str,
) -> ShiftSourceDocument:
    raw = (root / path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError("Outbound shift raw source changed after pin verification")
    return ShiftSourceDocument(key, path, raw, expected)


def _documents(
    base: Path,
    package: AdaptationPackage,
) -> tuple[ShiftSourceDocument, ...]:
    return (
        _raw_source(
            base, "c10_input", PREFIX + "baseline-input-v3.json", package.baseline_input_sha256
        ),
        _raw_source(
            base,
            "c10_assignment",
            PREFIX + "baseline-assignment-v3.json",
            package.baseline_assignment_sha256,
        ),
        ShiftSourceDocument(
            "c11_input",
            INPUT_PATH,
            package._raw[INPUT_PATH],
            sha256(package._raw[INPUT_PATH]).hexdigest(),
        ),
    )


def _postshift(
    bundle: V3Bundle,
    package: AdaptationPackage,
    baseline: WorkloadSource,
) -> tuple[WorkloadSource, tuple[str, ...]]:
    before = package.base_document("baseline-input-v3.json")["skus"]
    after = package.document(INPUT_PATH)["skus"]
    rows, excluded = project_rows(before, after)
    ports = {port.port_id: port for port in bundle.ports}
    raw = tuple(("c11/" + entry.path, entry.raw_sha256) for entry in package.entries)
    canonical = tuple(
        ("c11/" + entry.path, sha256_hex(package.document(entry.path))) for entry in package.entries
    )
    result = replace(
        baseline,
        outbound_weights=_weights(rows, "outbound", ports),
        raw_fingerprints=tuple(sorted((*baseline.raw_fingerprints, *raw))),
        document_fingerprints=tuple(sorted((*baseline.document_fingerprints, *canonical))),
    )
    validate_workload_source(result)
    return result, excluded


def load_outbound_shift_scenario(base: Path, adaptation: Path) -> N1Scenario:
    bundle = load_v3_bundle(base)
    package = load_adaptation_package(adaptation, base)
    baseline = load_workload_source(bundle)
    postshift, excluded = _postshift(bundle, package, baseline)
    scenario = N1Scenario(
        SCENARIO_VERSION,
        "N1",
        PROJECTION_POLICY,
        ("skus[].outbound_port_mix",),
        baseline,
        postshift,
        tuple(
            BaselinePlacement(hu.handling_unit_id, hu.sku_id, hu.slot_id, hu.module_id)
            for hu in sorted(bundle.handling_units, key=lambda hu: hu.handling_unit_id)
        ),
        _documents(base, package),
        package.source_revision,
        SCENARIO_ID,
        PERIOD_UNIT,
        excluded,
        "",
    )
    return replace(scenario, scenario_hash=sha256_hex(scenario_record(scenario)))


def verify_outbound_shift_scenario(scenario: N1Scenario) -> N1Scenario:
    if type(scenario) is not N1Scenario:
        raise ValueError("Exact authenticated N1Scenario required")
    expected = load_outbound_shift_scenario(*source_roots())
    require_same_authority(scenario, expected)
    return expected
