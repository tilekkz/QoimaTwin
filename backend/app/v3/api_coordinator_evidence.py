"""Bind outer source CLI evidence without modifying any namespace3 native payload."""

from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.input_pin import LAYOUT_VERSION
from app.v3.interface import Json

OUTER_FILES = ("profile.json", "request.json", "result.json")


def evidence_files(root: Path, snapshot: Json, run: Json) -> dict[str, bytes]:
    if root.is_symlink() or {p.name for p in root.iterdir()} != {*OUTER_FILES, "run"}:
        raise ValueError("coordinator CLI evidence directory differs")
    if any((root / name).is_symlink() for name in (*OUTER_FILES, "run")):
        raise ValueError("coordinator CLI evidence must be local regular files")
    raw = {name: (root / name).read_bytes() for name in OUTER_FILES}
    for name, key in (("profile.json", "profile_sha256"), ("request.json", "request_sha256")):
        if sha256(raw[name]).hexdigest() != snapshot[key]:
            raise ValueError("coordinator CLI evidence differs from registered inputs")
    if sha256((root / "run/inputs.json").read_bytes()).hexdigest() != snapshot["frozen_inputs"]:
        raise ValueError("coordinator native inputs differ from registration")
    request = parse_json(raw["request.json"])
    for key in ("input_hash", "registry_common_hash"):
        if request[key] != snapshot[key] or run[key] != snapshot[key]:
            raise ValueError("coordinator request/native identity differs")
    check_result(
        parse_json(raw["result.json"]),
        run,
        snapshot["request_sha256"],
        sha256((root / "run/manifest.json").read_bytes()).hexdigest(),
    )
    return raw


def check_result(result: Json, run: Json, request: str, manifest_hash: str) -> None:
    expected = {
        **{
            key: run[key]
            for key in (
                "status",
                "run_id",
                "input_hash",
                "registry_common_hash",
                "observed_until_tick",
                "metrics",
            )
        },
        "request_sha256": request,
        "manifest_sha256": manifest_hash,
        "layout_version": LAYOUT_VERSION,
        "operational_admission": False,
    }
    if type(result) is not dict or result.keys() != expected.keys() | {"manifest", "request"}:
        raise ValueError("coordinator CLI result fields differ")
    if any(type(result[key]) is not str or not result[key] for key in ("manifest", "request")):
        raise ValueError("coordinator CLI provenance paths must be text")
    if canonical_bytes({key: result[key] for key in expected}) != canonical_bytes(expected):
        raise ValueError("coordinator CLI result contradicts native observations")
