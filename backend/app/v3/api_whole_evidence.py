"""Outer CLI evidence is bound separately; native transport bytes remain unchanged."""

from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.interface import Json

OUTER_FILES = ("profile.json", "request.json", "result.json")


def evidence_files(root: Path, snapshot: Json, run: Json, manifest: Json) -> dict[str, bytes]:
    if root.is_symlink() or {p.name for p in root.iterdir()} != {*OUTER_FILES, "run"}:
        raise ValueError("whole CLI evidence directory differs")
    raw = {name: (root / name).read_bytes() for name in OUTER_FILES}
    for name, key in (("profile.json", "profile_sha256"), ("request.json", "request_sha256")):
        if sha256(raw[name]).hexdigest() != snapshot[key]:
            raise ValueError("whole CLI evidence differs from registered inputs")
    if sha256((root / "run/inputs.json").read_bytes()).hexdigest() != snapshot["frozen_inputs"]:
        raise ValueError("whole CLI native inputs differ from registration")
    request = parse_json(raw["request.json"])
    for key in ("input_hash", "physical_input_hash"):
        if request[key] != snapshot[key] or run[key] != snapshot[key]:
            raise ValueError("whole CLI request/native identity differs")
    check_result(
        parse_json(raw["result.json"]),
        run,
        manifest,
        snapshot["request_sha256"],
        sha256((root / "run/manifest.json").read_bytes()).hexdigest(),
    )
    return raw


def check_result(result: Json, run: Json, manifest: Json, request: str, manifest_hash: str) -> None:
    expected = {
        **{
            k: run[k]
            for k in (
                "status",
                "run_id",
                "input_hash",
                "physical_input_hash",
                "metrics",
                "capabilities",
            )
        },
        "request_sha256": request,
        "manifest_sha256": manifest_hash,
        "event_chunks": len(manifest["event_chunks"]),
        "checkpoint_chunks": len(manifest["checkpoint_chunks"]),
        "layout_version": LAYOUT_VERSION,
        "operational_admission": False,
    }
    if type(result) is not dict or result.keys() != expected.keys() | {"manifest", "request"}:
        raise ValueError("whole CLI result fields differ")
    if any(type(result[k]) is not str or not result[k] for k in ("manifest", "request")):
        raise ValueError("whole CLI provenance paths must be text")
    if canonical_bytes({k: result[k] for k in expected}) != canonical_bytes(expected):
        raise ValueError("whole CLI result contradicts actual native observations")
