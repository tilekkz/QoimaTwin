"""Bounded replay windows; descriptors retain hashes of exact uncompressed file bytes."""

from itertools import pairwise

from app.api.context import Json
from app.errors import AppError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore, require_identifier
from app.storage.canonical_json import parse_json

MAX_WINDOW_BYTES = 8_000_000


class RunNotFound(AppError):
    code = "run_not_found"
    http_status = 404


class WindowTooLarge(AppError):
    code = "chunk_window_too_large"
    http_status = 413


def manifest(store: ArtifactStore, run_id: str) -> Json:
    result = store.read_reference("runs", run_id)
    if result is None:
        raise RunNotFound(f"unknown run: {run_id}")
    return dict(result)


def manifest_with_catalog(store: ArtifactStore, run_id: str) -> Json:
    result = manifest(store, run_id)
    result["catalog_data"] = store.read_json("run_files", result["catalog"]["sha256"])
    return result


def chunk_window(store: ArtifactStore, run_id: str, from_s: float, limit: int) -> Json:
    run = manifest(store, run_id)
    source: list[Json] = run["event_chunks"] if "event_chunks" in run else run["chunks"]
    chunks = [row for row in source if row["end_s"] > from_s]
    selected = chunks[:limit]
    snapshots = snapshot_chain(run, from_s)
    if sum(row["bytes"] for row in selected + snapshots) > MAX_WINDOW_BYTES:
        raise WindowTooLarge("requested chunk window exceeds 8 MB; reduce limit")
    return {
        "run_id": run_id,
        "from_s": from_s,
        "chunks": payloads(store, selected),
        "snapshots": payloads(store, snapshots),
        "next_from_s": selected[-1]["end_s"] if selected and len(chunks) > limit else None,
    }


def payloads(store: ArtifactStore, rows: list[Json]) -> list[Json]:
    return [
        {"descriptor": row, "payload": parse_json(store.read_bytes("run_files", row["sha256"]))}
        for row in rows
    ]


def snapshot_chain(run: Json, from_s: float) -> list[Json]:
    eligible = [row for row in run.get("snapshot_chunks", []) if row["start_s"] <= from_s]
    if not eligible:
        return []
    bases = [index for index, row in enumerate(eligible) if row["encoding"] == "full"]
    if not bases:
        raise ArtifactCorruption("snapshot seek has no full checkpoint base")
    chain = eligible[bases[-1] :]
    for previous, row in pairwise(chain):
        if row["base_at_s"] != previous["start_s"]:
            raise ArtifactCorruption("snapshot seek delta chain is broken")
    return list(chain)


def raw_file(store: ArtifactStore, run_id: str, identifier: str) -> bytes:
    require_identifier(identifier)
    run = manifest(store, run_id)
    references = [
        run["catalog"],
        *run.get("chunks", []),
        *run.get("event_chunks", []),
        *run.get("snapshot_chunks", []),
    ]
    if identifier not in {row["sha256"] for row in references}:
        raise RunNotFound("file is not referenced by this run's replay bundle")
    raw = store.read_bytes("run_files", identifier)
    if len(raw) > MAX_WINDOW_BYTES:
        raise WindowTooLarge("replay file exceeds the 8 MB response limit")
    return raw
