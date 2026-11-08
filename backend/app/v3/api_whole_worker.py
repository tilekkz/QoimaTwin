"""One owned whole job reuses the source CLI, with nested native and outer inventories."""

import tempfile
from pathlib import Path

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_whole_binding import verified_registration
from app.v3.api_whole_evidence import evidence_files
from app.v3.api_whole_identity import check_manifest_inventory, public_run_id, verified_response
from app.v3.api_whole_inputs import DOMAIN, FrozenWholeProfile, restore_inputs
from app.v3.api_whole_registry import load_registered
from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json
from app.v3.whole_cli import simulate_whole_file
from app.v3.whole_profile_io import compile_whole_profile
from app.v3.whole_profile_io_verify import verify_compiled
from app.v3.whole_run_validation import run_identity
from app.v3.whole_transport import read_whole_run


def whole_job(job: Job) -> Json:
    store = ArtifactStore(Path(job.store_root))
    evidence = store.root / "whole-v3-evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=evidence))
    try:
        frozen = load_registered(store, job.payload["whole_bundle_id"])
        profile, snapshot = restore_inputs(store, frozen.bundle_id, attempt / "source")
        _preflight(attempt / "source", profile, snapshot)
        result = simulate_whole_file(attempt / "source", profile, attempt / "output")
        if result["status"] not in {"complete", "partial"}:
            raise RuntimeError("whole CLI reported a failed attempt")
        return publish_output(store, frozen, attempt / "output")
    except Exception as exc:
        (attempt / "failure.json").write_bytes(
            canonical_bytes(
                {"domain": DOMAIN, "status": "failed", "exception_type": type(exc).__name__}
            )
        )
        if isinstance(exc, ValueError):
            raise InvalidInputError("registered whole validation failed") from exc
        raise UnexpectedExecutionError("whole execution or publication failed") from exc


def _preflight(source: Path, profile: Path, snapshot: Json) -> None:
    bundle = load_v3_bundle(source)
    compiled = compile_whole_profile(
        bundle, load_conveyor_source(bundle), parse_json(profile.read_bytes())
    )
    verify_compiled(compiled)
    if (
        compiled.choices_sha256,
        compiled.run_inputs.input_hash,
        compiled.run_inputs.physical_input_hash,
    ) != (snapshot["profile_sha256"], snapshot["input_hash"], snapshot["physical_input_hash"]):
        raise ValueError("restored whole choices differ from registration before engine")


def publish_output(store: ArtifactStore, frozen: FrozenWholeProfile, output: Path) -> Json:
    snapshot = verified_registration(store, frozen)
    run = read_whole_run(output / "run")
    if run["input_hash"] != snapshot["input_hash"] or run["run_id"] != run_identity(
        snapshot["input_hash"]
    ):
        raise ValueError("whole native run differs from registration")
    manifest = parse_json((output / "run/manifest.json").read_bytes())
    raw = evidence_files(output, snapshot, run, manifest)
    identifier = public_run_id(run["run_id"], frozen.bundle_id)
    index = {
        "domain": DOMAIN,
        "run_id": identifier,
        "native_run_id": run["run_id"],
        "input_bundle_id": frozen.bundle_id,
        "input_hash": run["input_hash"],
        "physical_input_hash": run["physical_input_hash"],
        "request_sha256": snapshot["request_sha256"],
        "files": index_files(store, output / "run"),
        "request_files": [
            {"path": name, "bytes": len(value), "sha256": store.put_bytes("run_files", value)}
            for name, value in sorted(raw.items())
        ],
    }
    check_manifest_inventory(manifest, index)
    response = verified_response(run, index)
    store.publish_reference("runs", identifier, index)
    return response


def index_files(store: ArtifactStore, root: Path) -> list[Json]:
    return [
        {
            "path": p.relative_to(root).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": store.put_bytes("run_files", p.read_bytes()),
        }
        for p in sorted(root.rglob("*.json"))
    ]
