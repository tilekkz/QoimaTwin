"""Strict GLB2 binary reader; unsupported geometry never disappears silently."""

import hashlib
import json
import math
import struct

import numpy as np

from app.v3.mesh_proof_accessors import primitive
from app.v3.mesh_proof_json import Document, entry, integer, items, obj, unsupported
from app.v3.mesh_proof_scene import RigidScene, Solid, components
from app.v3.mesh_proof_transform import decode_nodes
from app.v3.mesh_proof_types import MeshProofError


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MeshProofError("duplicate GLB JSON key")
        result[key] = value
    return result


def _finite(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise MeshProofError("nonfinite GLB JSON number")
    return result


def _chunks(payload: bytes) -> tuple[Document, bytes]:
    if len(payload) < 28 or len(payload) > 64 * 1024 * 1024:
        raise MeshProofError("unsupported GLB length")
    magic, version, length = struct.unpack_from("<4sII", payload)
    if magic != b"glTF" or version != 2 or length != len(payload):
        raise MeshProofError("invalid GLB2 header")
    cursor, chunks = 12, []
    for expected in (0x4E4F534A, 0x004E4942):
        if cursor + 8 > length:
            raise MeshProofError("missing GLB chunk")
        size, kind = struct.unpack_from("<II", payload, cursor)
        cursor += 8
        if kind != expected or size % 4 or cursor + size > length:
            raise MeshProofError("invalid GLB chunk bounds or order")
        chunks.append(payload[cursor : cursor + size])
        cursor += size
    if cursor != length:
        raise MeshProofError("unexpected GLB chunks")
    document = obj(
        json.loads(
            chunks[0], object_pairs_hook=_object, parse_constant=_finite, parse_float=_finite
        )
    )
    return document, chunks[1]


def _parts(document: Document, binary: bytes, allow_collinear: bool) -> tuple[Solid, ...]:
    result: list[Solid] = []
    used: set[int] = set()
    for index, node in enumerate(items(document["nodes"])):
        node = obj(node)
        if "mesh" not in node:
            continue
        mesh_id = integer(node["mesh"])
        used.add(mesh_id)
        mesh = entry(document, "meshes", mesh_id)
        unsupported(mesh, ("weights", "extensions"))
        triangles = [primitive(document, binary, obj(p)) for p in items(mesh.get("primitives"))]
        if not triangles:
            raise MeshProofError("empty mesh")
        for part, solid in enumerate(
            components(np.concatenate(triangles), allow_collinear=allow_collinear)
        ):
            result.append(Solid(index, f"{node.get('name', index)}:{part}", solid))
    if used != set(range(len(items(document.get("meshes"))))):
        raise MeshProofError("unreferenced mesh is unsupported")
    return tuple(result)


def load_glb(payload: bytes, expected_sha256: str, *, allow_collinear: bool = False) -> RigidScene:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise MeshProofError("mesh hash mismatch")
    try:
        document, binary = _chunks(payload)
        if obj(document.get("asset")).get("version") != "2.0":
            raise MeshProofError("unsupported GLTF version")
        unsupported(document, ("skins", "animations", "extensionsRequired", "extensions"))
        buffers = items(document.get("buffers"))
        if len(buffers) != 1 or "uri" in obj(buffers[0]):
            raise MeshProofError("only one embedded GLB buffer is supported")
        length = integer(obj(buffers[0]).get("byteLength"), 1)
        if not 0 <= len(binary) - length <= 3:
            raise MeshProofError("invalid embedded buffer length")
        return RigidScene(
            digest, decode_nodes(document), _parts(document, binary[:length], allow_collinear)
        )
    except (KeyError, TypeError, OverflowError, UnicodeError, json.JSONDecodeError) as error:
        raise MeshProofError("invalid GLB geometry document") from error
