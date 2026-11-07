"""Allowlisted fingerprints and verified raw artifacts for the manual benchmark."""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes

type Json = dict[str, Any]
IDENTITY_KEYS = (
    "run_id",
    "events_sha256",
    "input_hash",
    "proposal_sha256",
    "profile_sha256",
    "source_sha256",
    "git_revision",
    "engine_version",
    "horizon_tick",
    "end_tick",
    "graph_sha256",
    "source_revision",
    "artifacts_sha256",
    "operational_status",
)


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def source_state(backend: Path) -> Json:
    paths = list((backend / "app").rglob("*.py"))
    paths += list((backend / "tools").glob("benchmark_v3*.py"))
    if any(
        path.is_symlink() or not path.resolve().is_relative_to(backend.resolve()) for path in paths
    ):
        raise ValueError("source fingerprint refuses linked files outside its allowlist")
    files = {
        path.relative_to(backend).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }
    return {"source_sha256": digest(files), "source_files": files}


def determinism(runs: list[Json]) -> dict[str, bool]:
    if len(runs) < 2:
        raise ValueError("determinism needs at least two repeats")
    return {
        key: all(run.get(key) is not None and run[key] == runs[0].get(key) for run in runs)
        for key in IDENTITY_KEYS
    }


def artifact_inventory(root: Path) -> Json:
    manifest = json.loads((root / "manifest.json").read_bytes())
    descriptors = [manifest["metadata"], manifest["graph_document"]]
    descriptors += manifest["event_chunks"] + manifest["snapshot_chunks"]
    result = {}
    for row in descriptors:
        path = root / row["path"]
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("artifact path escapes output")
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if len(raw) != row["bytes"] or sha != row["sha256"]:
            raise ValueError("artifact raw bytes/hash mismatch")
        if row["path"] in result:
            raise ValueError("duplicate artifact descriptor")
        result[row["path"]] = {"bytes": len(raw), "sha256": sha}
    raw = (root / "manifest.json").read_bytes()
    result["manifest.json"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return result


def exclusive_json(path: Path, value: object) -> None:
    with path.open("xb") as handle:
        handle.write(canonical_bytes(value))
