"""Versioned immutable saved-pair identity binds every raw member; index publishes last."""

from hashlib import sha256

from app.errors import AppError, InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import sha256_hex
from app.v3.coordinator_transport_schema import digest, reference
from app.v3.interface import Json
from app.v3.relocation_pair_publication_source import (
    ARMS,
    MAX_MEMBERS,
    MAX_PAIR_BYTES,
    SavedPair,
    descriptor,
    validate,
)
from app.v3.workload_policy import fields

DOMAIN = "qoima-saved-relocation-pair-publication-0.1.0"
INDEX_FIELDS = {"domain", "pair_id", "pair_input_hash", "comparison_sha256", "files"}


class UnknownPair(AppError):
    code = "unknown_relocation_pair"
    http_status = 404


def public_id(index: Json) -> str:
    return sha256_hex({key: value for key, value in index.items() if key != "pair_id"})


def publish(store: ArtifactStore, saved: SavedPair) -> Json:
    raw = dict(saved.members)
    index: Json = {
        "domain": DOMAIN,
        "pair_input_hash": sha256(raw["inputs.json"]).hexdigest(),
        "comparison_sha256": sha256(raw["comparison.json"]).hexdigest(),
        "files": [descriptor(name, body) for name, body in saved.members],
    }
    index["pair_id"] = public_id(index)
    for _, body in saved.members:
        store.put_bytes("run_files", body)
    store.publish_reference("runs", index["pair_id"], index)
    return response(index, saved)


def _index(value: object, identifier: str) -> Json:
    index = fields(value, INDEX_FIELDS)
    for key in ("pair_id", "pair_input_hash", "comparison_sha256"):
        digest(index[key])
    if index["pair_id"] != identifier or public_id(index) != identifier:
        raise ValueError("Saved pair public identity differs from complete index")
    rows = index["files"]
    if type(rows) is not list or not 0 < len(rows) <= MAX_MEMBERS:
        raise ValueError("Saved pair index inventory is unbounded")
    for row in rows:
        reference(row, set())
    names = [row["path"] for row in rows]
    if names != sorted(set(names)) or sum(row["bytes"] for row in rows) > MAX_PAIR_BYTES:
        raise ValueError("Saved pair index inventory is duplicated or unbounded")
    for name, key in (("inputs.json", "pair_input_hash"), ("comparison.json", "comparison_sha256")):
        if [row["sha256"] for row in rows if row["path"] == name] != [index[key]]:
            raise ValueError("Saved pair index input/comparison identity differs")
    return index


def known(store: ArtifactStore, identifier: str) -> Json:
    try:
        value = store.read_reference("runs", identifier)
        if value is None or (type(value) is dict and value.get("domain") != DOMAIN):
            raise UnknownPair("Unknown saved relocation pair")
        return _index(value, identifier)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("Saved pair index identity or structure is invalid") from exc


def arm_files(index: Json, arm: str) -> list[Json]:
    if arm not in ARMS:
        raise UnknownPair("Unknown relocation pair arm")
    prefix = arm + "/"
    return [
        {**row, "path": row["path"][len(prefix) :]}
        for row in index["files"]
        if row["path"].startswith(prefix)
    ]


def member(index: Json, arm: str, identifier: str) -> str:
    selected = [row["path"] for row in arm_files(index, arm) if row["sha256"] == identifier]
    if not selected:
        raise UnknownPair("Unknown member of selected relocation pair arm")
    return str(arm + "/" + selected[0])


def checked(store: ArtifactStore, identifier: str) -> tuple[Json, SavedPair]:
    index = known(store, identifier)
    try:
        members = []
        for row in index["files"]:
            raw = store.read_bytes("run_files", row["sha256"])
            if len(raw) != row["bytes"]:
                raise ValueError("Saved pair member length differs")
            members.append((row["path"], raw))
        saved = validate(tuple(members))
        if saved.pair.input_hash != index["pair_input_hash"]:
            raise ValueError("Saved pair native input identity differs from index")
        return index, saved
    except (ValueError, TypeError, KeyError, OSError, InvalidInputError) as exc:
        raise ArtifactCorruption("Saved pair strict native validation failed") from exc


def identity(index: Json, saved: SavedPair, arm: str) -> Json:
    position = ARMS.index(arm)
    run = saved.runs[position]
    return {
        "pair_id": index["pair_id"],
        "arm": arm,
        "native_run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "pair_input_hash": index["pair_input_hash"],
        "common_input_hash": run["common_input_hash"],
        "registry_common_hash": run["registry_common_hash"],
    }


def response(index: Json, saved: SavedPair) -> Json:
    return {
        "schema_version": DOMAIN,
        "pair_id": index["pair_id"],
        "origin": "verified_saved_native_pair",
        "producer_attestation": False,
        "full_n1_acceptance": False,
        "comparison": saved.comparison,
        "arms": {arm: identity(index, saved, arm) for arm in ARMS},
    }
