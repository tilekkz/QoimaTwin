"""Execute one source-bound shared whole flow from explicit public JSON choices."""

from hashlib import sha256
from pathlib import Path

from app.errors import AppError, InvalidInputError, error_report
from app.storage.canonical_json import parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.whole_cli_evidence import finish, freeze_request, reserve
from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_profile_io import CompiledWholeProfile, compile_whole_profile
from app.v3.whole_run import build_whole_run
from app.v3.whole_transport import write_whole_run


def simulate_whole_file(bundle_path: Path, profile_path: Path, out: Path) -> Json:
    reserve(out)
    document = parse_json(profile_path.read_bytes())
    bundle = load_v3_bundle(bundle_path)
    conveyor = load_conveyor_source(bundle)
    compiled = compile_whole_profile(bundle, conveyor, document)
    request_hash = freeze_request(compiled, out)
    try:
        report = _run(compiled, conveyor, out / "run")
    except AppError as exc:
        report = error_report(exc)
    except (OSError, ValueError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    except RuntimeError as exc:
        report = error_report(exc)
    return finish(out, request_hash, report)


def _run(compiled: CompiledWholeProfile, conveyor: ConveyorSource, out: Path) -> Json:
    inputs = compiled.run_inputs
    outcome = WholeFlowEngine(inputs.profile, conveyor).run(inputs.horizon_tick, inputs.end_tick)
    run = build_whole_run(inputs, outcome, validate=False)
    manifest = write_whole_run(run, out, inputs=inputs.frozen_bytes)
    return {
        "status": run["status"],
        "run_id": manifest["run_id"],
        "input_hash": inputs.input_hash,
        "physical_input_hash": inputs.physical_input_hash,
        "manifest": str(out / "manifest.json"),
        "manifest_sha256": sha256((out / "manifest.json").read_bytes()).hexdigest(),
        "metrics": run["metrics"],
        "capabilities": run["capabilities"],
        "event_chunks": len(manifest["event_chunks"]),
        "checkpoint_chunks": len(manifest["checkpoint_chunks"]),
    }
