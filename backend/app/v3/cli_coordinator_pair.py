"""Source-only N0/N4 CLI: freeze both requests, execute independently, publish both runs."""

from hashlib import sha256
from pathlib import Path

from app.errors import AppError, InvalidInputError, error_report
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_source import load_conveyor_source
from app.v3.coordinator_cli_evidence import reserve
from app.v3.coordinator_pair import compare_coordinator_profiles, prepare_coordinator_pair
from app.v3.coordinator_pair_models import (
    PAIR_VERSION,
    CoordinatorPairResult,
    PreparedCoordinatorPair,
)
from app.v3.coordinator_transport import write_coordinator_run
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.run_publication import publish

REQUEST_VERSION = "qoima-coordinator-pair-cli-request-0.1.0"


def _freeze(prepared: PreparedCoordinatorPair, out: Path) -> str:
    reserve(out)
    files = []
    for side, compiled in (("baseline", prepared.baseline), ("candidate", prepared.candidate)):
        choices = parse_json(compiled.frozen_bytes)["choices"]
        files.append(publish(out, side + "-profile.json", canonical_bytes(choices)))
        files.append(publish(out, side + "/inputs.json", compiled.frozen_bytes))
    request = {
        "request_version": REQUEST_VERSION,
        "pair_version": PAIR_VERSION,
        "scenario": prepared.scenario,
        "common_input_hash": prepared.common_input_hash,
        "baseline_input_hash": prepared.baseline.input_hash,
        "candidate_input_hash": prepared.candidate.input_hash,
        "files": files,
    }
    raw = canonical_bytes(request)
    publish(out, "request.json", raw)
    return sha256(raw).hexdigest()


def _publish(result: CoordinatorPairResult, prepared: PreparedCoordinatorPair, out: Path) -> Json:
    if (result.baseline_inputs, result.candidate_inputs) != (
        prepared.baseline.frozen_bytes,
        prepared.candidate.frozen_bytes,
    ):
        raise ValueError("Pair execution input differs from the frozen public request")
    manifests = []
    for name, run, raw in (
        ("baseline", result.baseline_run, result.baseline_inputs),
        ("candidate", result.candidate_run, result.candidate_inputs),
    ):
        write_coordinator_run(run, out / name, inputs=raw)
        path = out / name / "manifest.json"
        payload = path.read_bytes()
        manifests.append(
            {
                "path": name + "/manifest.json",
                "bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        )
    report = result.report
    partial = any(report[side]["status"] == "partial" for side in ("baseline", "candidate"))
    return {
        "status": "partial" if partial else "complete",
        "comparison": report,
        "native_manifests": manifests,
    }


def compare_coordinator_files(
    bundle_path: Path,
    baseline_path: Path,
    candidate_path: Path,
    scenario: str,
    out: Path,
) -> Json:
    reserve(out)
    baseline, candidate = (
        parse_json(baseline_path.read_bytes()),
        parse_json(candidate_path.read_bytes()),
    )
    bundle = load_v3_bundle(bundle_path)
    conveyor = load_conveyor_source(bundle)
    prepared = prepare_coordinator_pair(bundle, conveyor, baseline, candidate, scenario=scenario)
    request_hash = _freeze(prepared, out)
    try:
        result = compare_coordinator_profiles(
            bundle, conveyor, baseline, candidate, scenario=scenario
        )
        report = _publish(result, prepared, out)
    except AppError as exc:
        report = error_report(exc)
    except (OSError, ValueError) as exc:
        report = error_report(InvalidInputError(str(exc)))
    except Exception as exc:
        report = error_report(exc)
    report.update(
        request_sha256=request_hash,
        request=str(out / "request.json"),
        layout_version=LAYOUT_VERSION,
        operational_admission=False,
    )
    publish(out, "result.json", canonical_bytes(report))
    return report
