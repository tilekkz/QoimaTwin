"""Tiny independent GLB binary exercises bounds, hierarchy and rigid transforms."""

import hashlib
import json
import struct
from typing import Any

import numpy as np
import pytest

from app.v3.mesh_proof_glb import load_glb
from app.v3.mesh_proof_types import MeshProofError
from tests.v3.test_mesh_proof_geometry import box_triangles


def fixture_document() -> tuple[dict[str, Any], bytes]:
    triangles = box_triangles((0, 0, 0), (1, 1, 1))
    positions = triangles.astype("<f4").tobytes()
    indices = np.arange(36, dtype="<u2").tobytes()
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [
            {"name": "root", "translation": [2, 0, 0], "children": [1]},
            {"name": "cube", "mesh": 0},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(positions) + len(indices)}],
        "bufferViews": [
            {"buffer": 0, "byteLength": len(positions)},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices)},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 36, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"},
        ],
    }
    return document, positions + indices


def encode_glb(document: dict[str, Any], binary: bytes) -> bytes:
    header = json.dumps(document, separators=(",", ":")).encode()
    header += b" " * (-len(header) % 4)
    binary += b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(header), 0x4E4F534A) + header
    chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<4sII", b"glTF", 2, len(chunks) + 12) + chunks


def test_decode_real_binary_and_parent_transform() -> None:
    payload = encode_glb(*fixture_document())
    scene = load_glb(payload, hashlib.sha256(payload).hexdigest())
    assert [node.name for node in scene.nodes] == ["root", "cube"]
    assert len(scene.parts) == 1
    points = scene.world_parts()[0].triangles.reshape(-1, 3)
    np.testing.assert_allclose(points.min(axis=0), [2, 0, 0])
    np.testing.assert_allclose(points.max(axis=0), [3, 1, 1])
    with pytest.raises(ValueError):
        scene.parts[0].triangles[0, 0, 0] = 7
    with pytest.raises(ValueError):
        scene.parts[0].triangles.flags.writeable = True


@pytest.mark.parametrize(
    "kind",
    [
        "hash",
        "length",
        "scale",
        "cycle",
        "duplicate_parent",
        "sparse",
        "bounds",
        "mode",
        "skin",
        "morph",
        "extension",
        "nan",
    ],
)
def test_malformed_or_unsupported_glb_is_rejected(kind: str) -> None:
    doc, binary = fixture_document()
    if kind == "scale":
        doc["nodes"][0]["scale"] = [1, 2, 1]
    elif kind == "cycle":
        doc["nodes"][1]["children"] = [0]
    elif kind == "duplicate_parent":
        doc["scenes"][0]["nodes"].append(1)
    elif kind in ("sparse", "bounds"):
        doc["accessors"][0][{"sparse": "sparse", "bounds": "byteOffset"}[kind]] = (
            {} if kind == "sparse" else 9999
        )
    elif kind == "mode":
        doc["meshes"][0]["primitives"][0]["mode"] = 5
    elif kind == "skin":
        doc["nodes"][1]["skin"] = 0
    elif kind == "morph":
        doc["meshes"][0]["primitives"][0]["targets"] = [{}]
    elif kind == "extension":
        doc["extensionsRequired"] = ["KHR_draco_mesh_compression"]
    elif kind == "nan":
        binary = struct.pack("<f", float("nan")) + binary[4:]
    payload = encode_glb(doc, binary)
    if kind == "length":
        payload += b"bad!"
    digest = "0" * 64 if kind == "hash" else hashlib.sha256(payload).hexdigest()
    with pytest.raises(MeshProofError):
        load_glb(payload, digest)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_metadata_is_not_valid_gltf(value: float) -> None:
    document, binary = fixture_document()
    document["extras"] = {"untrusted_value": value}
    payload = encode_glb(document, binary)
    with pytest.raises(MeshProofError, match="nonfinite"):
        load_glb(payload, hashlib.sha256(payload).hexdigest())
