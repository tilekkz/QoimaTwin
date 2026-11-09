"""Freeze source-bound request evidence before one actual coordinator execution."""

from hashlib import sha256
from pathlib import Path

from app.errors import OutputNotEmptyError, require_empty_output
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import COORDINATOR_VERSION
from app.v3.coordinator_profile import (
    COMPILER_VERSION,
    INPUT_SCOPE,
    CompiledCoordinatorProfile,
    validate_compiled_coordinator,
)
from app.v3.coordinator_run_schema import PUBLICATION_VERSION
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.interface import Json
from app.v3.run_publication import publish

REQUEST_VERSION = "qoima-coordinator-cli-request-0.1.0"


def reserve(out: Path) -> None:
    if out.is_symlink():
        raise OutputNotEmptyError("Coordinator output must not be a symbolic link")
    require_empty_output(out)


def freeze_request(
    compiled: CompiledCoordinatorProfile,
    conveyor: ConveyorSource,
    out: Path,
) -> str:
    reserve(out)
    validate_compiled_coordinator(compiled, conveyor)
    value = parse_json(compiled.frozen_bytes)
    if value["scope"] != INPUT_SCOPE:
        raise ValueError("Public coordinator CLI requires source-bound inputs")
    choices = canonical_bytes(value["choices"])
    reserve(out)
    profile = publish(out, "profile.json", choices)
    request = {
        "request_version": REQUEST_VERSION,
        "compiler_version": COMPILER_VERSION,
        "engine_version": COORDINATOR_VERSION,
        "export_version": PUBLICATION_VERSION,
        "scope": INPUT_SCOPE,
        "profile": profile,
        "choices_sha256": sha256(choices).hexdigest(),
        "input_hash": compiled.input_hash,
        "registry_common_hash": compiled.registry_common_hash,
        "horizon_tick": compiled.horizon_tick,
        "end_tick": compiled.end_tick,
        "inputs_path": "run/inputs.json",
    }
    raw = canonical_bytes(request)
    publish(out, "request.json", raw)
    publish(out / "run", "inputs.json", compiled.frozen_bytes)
    return sha256(raw).hexdigest()


def finish(out: Path, request_hash: str, report: Json) -> Json:
    report.update(
        request_sha256=request_hash,
        request=str(out / "request.json"),
        layout_version=LAYOUT_VERSION,
        operational_admission=False,
    )
    publish(out, "result.json", canonical_bytes(report))
    return report
