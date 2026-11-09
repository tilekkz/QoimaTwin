"""Offline immutable source bindings; the legacy V3 input bundle is unchanged."""

import hashlib
import json
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from app.v3.mesh_proof_glb import load_glb
from app.v3.mesh_proof_json import obj
from app.v3.mesh_proof_motion import Pose, Segment, validate_frames, validate_motion
from app.v3.mesh_proof_scene import RigidScene
from app.v3.mesh_proof_types import MeshProofError

MANIFEST_SHA256 = "8d3664e081e3906071ff70fdd00f274f047a498aeee98f3296f0e4c5cd4eddb7"
MESH_PATH = "frontend/public/models/v3/forklift-pallet-low-fixture.glb"
ACTION_PATH = "frontend/public/data/v3/pallet-pickup-cycle.json"


@dataclass(frozen=True, slots=True)
class Fixture:
    scene: RigidScene
    segments: tuple[Segment, ...]
    hashes: tuple[tuple[str, str], ...]


def load_fixture(root: Path) -> Fixture:
    try:
        manifest = (root / "provenance.json").read_bytes()
        if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA256:
            raise MeshProofError("proof supplement provenance mismatch")
        sources: dict[str, bytes] = {}
        hashes: list[tuple[str, str]] = []
        for record in json.loads(manifest)["files"]:
            raw = (root / record.get("stored_path", record["path"])).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            git_digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            if (
                len(raw) != record["bytes"]
                or digest != record["sha256"]
                or (git_digest != record["git_blob_sha1"])
            ):
                raise MeshProofError(f"bound source changed: {record['path']}")
            sources[record["path"]] = raw
            hashes.append((record["path"], digest))
        scene = load_glb(sources[MESH_PATH], dict(hashes)[MESH_PATH], allow_collinear=True)
        validate_frames(scene)
        keys = obj(json.loads(sources[ACTION_PATH]))["keys"]
        segments = tuple(
            Segment(
                i,
                a["phase"],
                Pose(a["root_z"], a["fork_top"], a["reach"]),
                Pose(b["root_z"], b["fork_top"], b["reach"]),
                a["attached"],
            )
            for i, (a, b) in enumerate(pairwise(keys))
        )
        validate_motion(segments)
        return Fixture(scene, segments, tuple(hashes))
    except OSError as error:
        raise MeshProofError("proof source missing or unreadable") from error
