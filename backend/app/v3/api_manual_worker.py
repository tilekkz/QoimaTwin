"""Spawn dispatch: use the CLI's real invariant engine/export pipeline, then publish."""

import tempfile
from pathlib import Path

from app.api.context import Job, Json
from app.api.errors import UnexpectedExecutionError
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3.api_manual_identity import public_run_id, verified_response
from app.v3.api_manual_inputs import DOMAIN, restore_inputs
from app.v3.cli_manual import simulate_manual


def manual_job(job: Job) -> Json:
    store = ArtifactStore(Path(job.store_root))
    evidence = store.root / "manual-v3-evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=evidence))
    try:
        proposal = restore_inputs(store, job.payload["manual_bundle_id"], attempt / "source")
        result = simulate_manual(attempt / "source", proposal, attempt / "output")
        return _publish(store, job, attempt / "output", result)
    except Exception as exc:
        (attempt / "failure.json").write_bytes(
            canonical_bytes(
                {"domain": DOMAIN, "status": "failed", "exception_type": type(exc).__name__}
            )
        )
        if isinstance(exc, ValueError):
            raise InvalidInputError("manual proposal validation failed") from exc
        raise UnexpectedExecutionError("manual execution or publication failed") from exc


def _publish(store: ArtifactStore, job: Job, output: Path, result: Json) -> Json:
    from app.v3.run_transport import read_manual_run, seek_manual_run

    run = read_manual_run(output / "run")
    seek_manual_run(output / "run", run["observed_until_tick"])
    metrics = (output / "metrics.json").read_bytes()
    if metrics != canonical_bytes(run["metrics"]):
        raise ValueError("manual metrics differ from validated run")
    files = []
    for path in sorted(output.rglob("*.json")):
        raw = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": store.put_bytes("run_files", raw),
                "bytes": len(raw),
            }
        )
    run_id = public_run_id(run["run_id"], job.payload["manual_bundle_id"])
    index = {
        "domain": DOMAIN,
        "run_id": run_id,
        "native_run_id": run["run_id"],
        "input_bundle_id": job.payload["manual_bundle_id"],
        "files": files,
    }
    store.publish_reference("runs", run_id, index)
    return verified_response(run, index)
