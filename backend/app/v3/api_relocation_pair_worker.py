"""One owned-worker strict pair authentication produces each immutable read response."""

from pathlib import Path

from app.api.context import Job, Json
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from app.v3.relocation_pair_publication_source import ARMS
from app.v3.relocation_pair_publication_storage import (
    arm_files,
    checked,
    identity,
    known,
    member,
    response,
)
from app.v3.relocation_replay import replay_relocation_run
from app.v3.workload_policy import fields

STREAM_VERSION = "qoima-saved-relocation-arm-ndjson-0.1.0"
ACTIONS = {"result", "manifest", "file", "replay", "bundle"}


def pair_read_job(job: Job) -> Json:
    payload = fields(job.payload, {"pair_id", "arm", "action", "artifact_id", "tick"})
    store = ArtifactStore(Path(job.store_root))
    preflight(store, payload)
    index, saved = checked(store, payload["pair_id"])
    action, arm = payload["action"], payload["arm"]
    if action == "result":
        return response(index, saved)
    position = ARMS.index(arm)
    metadata = identity(index, saved, arm)
    manifest = saved.manifests[position]
    rows = arm_files(index, arm)
    if action == "manifest":
        return {**metadata, "transport_manifest": manifest, "files": rows}
    raw = dict(saved.members)
    if action == "file":
        return {"body": raw[member(index, arm, payload["artifact_id"])], **metadata}
    if action == "bundle":
        stream_rows = [row for row in rows if row["path"] != "inputs.json"]
        header = {
            "record_type": "header",
            "schema_version": STREAM_VERSION,
            **metadata,
            "origin": "verified_saved_native_pair",
            "transport_manifest": manifest,
            "stream_descriptors": stream_rows,
        }
        bodies = tuple((row, raw[arm + "/" + row["path"]]) for row in stream_rows)
        return {"header": header, "members": bodies}
    tick = payload["tick"]
    if type(tick) is not int or not 0 <= tick <= saved.runs[position]["observed_until_tick"]:
        raise InvalidInputError("Replay tick must be an exactly observed nonnegative integer")
    replay = replay_relocation_run(
        saved.runs[position], inputs=raw[arm + "/inputs.json"], tick=tick
    )
    return {**metadata, "replay": replay}


def preflight(store: ArtifactStore, payload: Json) -> None:
    index = known(store, payload["pair_id"])
    action = payload["action"]
    if action not in ACTIONS:
        raise InvalidInputError("Unknown saved relocation pair read action")
    if action != "result":
        arm_files(index, payload["arm"])
    if action == "file":
        member(index, payload["arm"], payload["artifact_id"])
