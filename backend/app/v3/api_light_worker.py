"""Use the actual frozen-input CLI pipeline inside the existing shared spawned worker."""

import tempfile
from pathlib import Path

from app.api.context import Job, Json
from app.api.errors import UnexpectedExecutionError
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3.api_light_identity import public_run_id, verified_response
from app.v3.api_light_inputs import DOMAIN, restore_inputs
from app.v3.cli_lightflow import simulate_light_file
from app.v3.flow_run_validation import run_identity
from app.v3.flow_transport import read_flow_run


def light_job(job: Job) -> Json:
    store = ArtifactStore(Path(job.store_root))
    evidence = store.root / "light-v3-evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=evidence))
    try:
        profile, snapshot = restore_inputs(
            store, job.payload["light_bundle_id"], attempt / "source"
        )
        simulate_light_file(attempt / "source", profile, attempt / "output")
        return publish_output(store, job.payload["light_bundle_id"], attempt / "output", snapshot)
    except Exception as exc:
        (attempt / "failure.json").write_bytes(
            canonical_bytes(
                {"domain": DOMAIN, "status": "failed", "exception_type": type(exc).__name__}
            )
        )
        if isinstance(exc, ValueError):
            raise InvalidInputError("connected profile execution validation failed") from exc
        raise UnexpectedExecutionError("connected execution or publication failed") from exc


def publish_output(store: ArtifactStore, bundle_id: str, output: Path, snapshot: Json) -> Json:
    run = read_flow_run(output)
    if run["input_hash"] != snapshot["input_hash"] or run["run_id"] != run_identity(
        snapshot["input_hash"]
    ):
        raise ValueError("connected result differs from registered physical inputs")
    files = [
        {
            "path": p.relative_to(output).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": store.put_bytes("run_files", p.read_bytes()),
        }
        for p in sorted(output.rglob("*.json"))
    ]
    identifier = public_run_id(run["run_id"], bundle_id)
    index = {
        "domain": DOMAIN,
        "run_id": identifier,
        "native_run_id": run["run_id"],
        "input_bundle_id": bundle_id,
        "input_hash": run["input_hash"],
        "files": files,
    }
    response = verified_response(run, index)
    store.publish_reference("runs", identifier, index)
    return response
