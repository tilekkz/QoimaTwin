"""Restore verified native bytes for strict data-only reading, never engine restoration."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.storage.artifacts import ArtifactStore
from app.v3.api_coordinator_readers import file_bytes
from app.v3.api_manual_inputs import confined
from app.v3.coordinator_transport import read_coordinator_run
from app.v3.interface import Json


def native_run(store: ArtifactStore, index: Json, manifest: Json) -> tuple[Json, bytes]:
    """The caller first verifies registration, exact inventory and outer request evidence."""
    with TemporaryDirectory(prefix="qoima-coordinator-replay-") as temporary:
        root = Path(temporary)
        for row in index["files"]:
            path = confined(root, row["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file_bytes(store, index, row["sha256"]))
        run = read_coordinator_run(root)
        raw = confined(root, manifest["inputs"]["path"]).read_bytes()
    if run["run_id"] != index["native_run_id"] or run["input_hash"] != index["input_hash"]:
        raise ValueError("Coordinator replay native/public input identity mismatch")
    return run, raw
