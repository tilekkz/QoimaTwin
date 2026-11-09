"""Owned coordinator jobs preserve attempts and publish only verified namespace3 results."""

import tempfile
from pathlib import Path

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_coordinator_binding import verified_registration
from app.v3.api_coordinator_evidence import evidence_files
from app.v3.api_coordinator_identity import (
    check_manifest_inventory,
    manifest_descriptors,
    public_run_id,
    verified_response,
)
from app.v3.api_coordinator_inputs import DOMAIN, FrozenCoordinatorProfile, restore_inputs
from app.v3.api_coordinator_registry import load_registered
from app.v3.api_manual_inputs import confined
from app.v3.cli_coordinator import simulate_compiled_coordinator
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.coordinator_profile import (
    CompiledCoordinatorProfile,
    compile_coordinator_profile,
    validate_compiled_coordinator,
)
from app.v3.coordinator_run_identity import run_identity
from app.v3.coordinator_transport import read_coordinator_run
from app.v3.inputs import load_v3_bundle
from app.v3.interface import Json


def coordinator_job(job: Job) -> Json:
    store = ArtifactStore(Path(job.store_root))
    evidence = store.root / "coordinator-v3-evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=evidence))
    try:
        frozen = load_registered(store, job.payload["coordinator_bundle_id"])
        profile, snapshot = restore_inputs(store, frozen.bundle_id, attempt / "source")
        compiled, conveyor = _preflight(store, attempt / "source", profile, snapshot)
        result = simulate_compiled_coordinator(compiled, conveyor, attempt / "output")
        if result["status"] not in {"complete", "partial"}:
            raise RuntimeError("coordinator CLI reported a failed attempt")
        return publish_output(store, frozen, attempt / "output")
    except Exception as exc:
        (attempt / "failure.json").write_bytes(
            canonical_bytes(
                {
                    "domain": DOMAIN,
                    "status": "failed",
                    "exception_type": type(exc).__name__,
                }
            )
        )
        if isinstance(exc, ArtifactCorruption):
            raise
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            raise ArtifactCorruption(
                "registered coordinator evidence or publication is invalid"
            ) from exc
        raise UnexpectedExecutionError("coordinator execution or publication failed") from exc


def _preflight(
    store: ArtifactStore,
    source: Path,
    profile: Path,
    snapshot: Json,
) -> tuple[CompiledCoordinatorProfile, ConveyorSource]:
    bundle = load_v3_bundle(source)
    conveyor = load_conveyor_source(bundle)
    compiled = compile_coordinator_profile(bundle, conveyor, parse_json(profile.read_bytes()))
    validate_compiled_coordinator(compiled, conveyor)
    if (
        compiled.input_hash != snapshot["input_hash"]
        or compiled.registry_common_hash != snapshot["registry_common_hash"]
        or compiled.frozen_bytes != store.read_bytes("run_files", snapshot["frozen_inputs"])
    ):
        raise ValueError("restored coordinator input differs from registration before engine")
    return compiled, conveyor


def publish_output(store: ArtifactStore, frozen: FrozenCoordinatorProfile, output: Path) -> Json:
    snapshot = verified_registration(store, frozen)
    run = read_coordinator_run(output / "run")
    if run["input_hash"] != snapshot["input_hash"] or run["run_id"] != run_identity(
        snapshot["input_hash"],
    ):
        raise ValueError("coordinator native run differs from registration")
    manifest = parse_json((output / "run/manifest.json").read_bytes())
    raw = evidence_files(output, snapshot, run)
    identifier = public_run_id(run["run_id"], frozen.bundle_id)
    index = {
        "domain": DOMAIN,
        "run_id": identifier,
        "native_run_id": run["run_id"],
        "input_bundle_id": frozen.bundle_id,
        "input_hash": run["input_hash"],
        "registry_common_hash": run["registry_common_hash"],
        "request_sha256": snapshot["request_sha256"],
        "files": index_files(store, output / "run", manifest),
        "request_files": [
            {"path": name, "bytes": len(value), "sha256": store.put_bytes("run_files", value)}
            for name, value in sorted(raw.items())
        ],
    }
    check_manifest_inventory(manifest, index)
    response = verified_response(run, index)
    store.publish_reference("runs", identifier, index)
    return response


def index_files(store: ArtifactStore, root: Path, manifest: Json) -> list[Json]:
    names = {"manifest.json", *(row["path"] for row in manifest_descriptors(manifest))}
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if names != actual or root.is_symlink():
        raise ValueError("coordinator native output inventory differs")
    result: list[Json] = []
    for name in sorted(names):
        if (root / name).is_symlink():
            raise ValueError("coordinator native files must not be symbolic links")
        path = confined(root, name)
        raw = path.read_bytes()
        result.append(
            {"path": name, "bytes": len(raw), "sha256": store.put_bytes("run_files", raw)}
        )
    return result
