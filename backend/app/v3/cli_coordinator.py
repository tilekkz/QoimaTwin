"""Public source-only coordinator entry points; analytical fixtures stay non-public."""

from hashlib import sha256
from pathlib import Path

from app.errors import AppError, InvalidInputError, error_report
from app.storage.canonical_json import parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.coordinator_cli_evidence import finish, freeze_request, reserve
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_profile import CompiledCoordinatorProfile, compile_coordinator_profile
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_transport import write_coordinator_run
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json


def simulate_coordinator_file(bundle_path: Path, profile_path: Path, out: Path) -> Json:
    reserve(out)
    document = parse_json(profile_path.read_bytes())
    bundle = load_v3_bundle(bundle_path)
    conveyor = load_conveyor_source(bundle)
    compiled = compile_coordinator_profile(bundle, conveyor, document)
    return simulate_compiled_coordinator(compiled, conveyor, out)


def simulate_compiled_coordinator(
    compiled: CompiledCoordinatorProfile,
    conveyor: ConveyorSource,
    out: Path,
) -> Json:
    request_hash = freeze_request(compiled, conveyor, out)
    try:
        report = _run(compiled, conveyor, out / "run")
    except AppError as exc:
        report = error_report(exc)
    except (OSError, ValueError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    except Exception as exc:
        report = error_report(exc)
    return finish(out, request_hash, report)


def _run(compiled: CompiledCoordinatorProfile, conveyor: ConveyorSource, out: Path) -> Json:
    outcome = CoordinatorEngine(compiled.profile, conveyor).run(
        compiled.horizon_tick,
        compiled.end_tick,
    )
    run = build_coordinator_run(compiled, outcome)
    write_coordinator_run(run, out, inputs=compiled.frozen_bytes)
    return {
        "status": run["status"],
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "registry_common_hash": run["registry_common_hash"],
        "observed_until_tick": run["observed_until_tick"],
        "metrics": run["metrics"],
        "manifest": str(out / "manifest.json"),
        "manifest_sha256": sha256((out / "manifest.json").read_bytes()).hexdigest(),
    }
