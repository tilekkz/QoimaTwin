"""Only rigid, unit-scale GLTF node transforms enter a local proof."""

import numpy as np

from app.v3.mesh_proof_json import Document, entry, integer, items, obj, unsupported, vector
from app.v3.mesh_proof_scene import RigidNode
from app.v3.mesh_proof_types import Array, MeshProofError, readonly


def _rotation(quaternion: Array) -> Array:
    x, y, z, w = quaternion
    if abs(float(quaternion @ quaternion) - 1) > 1e-6:
        raise MeshProofError("rotation quaternion must be unit length")
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def local_matrix(node: Document) -> Array:
    unsupported(node, ("skin", "weights", "extensions"))
    if "matrix" in node:
        unsupported(node, ("translation", "rotation", "scale"))
        matrix = vector(node["matrix"], 16).reshape(4, 4).T.copy()
    else:
        if not np.array_equal(vector(node.get("scale", [1, 1, 1]), 3), np.ones(3)):
            raise MeshProofError("nonunit scale is unsupported")
        matrix = np.eye(4)
        matrix[:3, 3] = vector(node.get("translation", [0, 0, 0]), 3)
        matrix[:3, :3] = _rotation(vector(node.get("rotation", [0, 0, 0, 1]), 4))
    rotation = matrix[:3, :3]
    if (
        not np.array_equal(matrix[3], [0, 0, 0, 1])
        or not np.allclose(rotation.T @ rotation, np.eye(3), rtol=0, atol=1e-6)
        or abs(float(np.linalg.det(rotation)) - 1) > 1e-6
    ):
        raise MeshProofError("node transform is not rigid")
    return readonly(matrix)


def decode_nodes(document: Document) -> tuple[RigidNode, ...]:
    raw = [obj(value) for value in items(document.get("nodes"))]
    if not raw or len(raw) > 4096:
        raise MeshProofError("unsupported node count")
    parents: dict[int, int | None] = {}
    roots = items(entry(document, "scenes", document.get("scene", 0)).get("nodes"))

    def visit(index: object, parent: int | None, depth: int) -> None:
        position = integer(index)
        if position >= len(raw) or position in parents or depth > 100:
            raise MeshProofError("invalid, cyclic or shared node hierarchy")
        parents[position] = parent
        for child in items(raw[position].get("children", [])):
            visit(child, position, depth + 1)

    for root in roots:
        visit(root, None, 0)
    if len(parents) != len(raw):
        raise MeshProofError("unreferenced nodes are unsupported")
    names = [node.get("name", f"node:{i}") for i, node in enumerate(raw)]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(
        names
    ):
        raise MeshProofError("node names must be unique strings")
    return tuple(RigidNode(name, parents[i], local_matrix(raw[i])) for i, name in enumerate(names))
