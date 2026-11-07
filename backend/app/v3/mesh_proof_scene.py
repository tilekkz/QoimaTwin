"""Immutable rigid nodes and exact-position connected mesh components."""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from app.v3.mesh_proof_geometry import validate_solid
from app.v3.mesh_proof_types import Array, readonly


@dataclass(frozen=True, slots=True)
class RigidNode:
    name: str
    parent: int | None
    matrix: Array


@dataclass(frozen=True, slots=True)
class Solid:
    node: int
    name: str
    triangles: Array


@dataclass(frozen=True, slots=True)
class RigidScene:
    sha256: str
    nodes: tuple[RigidNode, ...]
    parts: tuple[Solid, ...]

    def matrices(self, translations: Mapping[str, Array] | None = None) -> tuple[Array, ...]:
        overrides = translations or {}
        result: dict[int, Array] = {}

        def resolve(index: int) -> Array:
            if index not in result:
                node = self.nodes[index]
                local = node.matrix.copy()
                if node.name in overrides:
                    local[:3, 3] = overrides[node.name]
                result[index] = local if node.parent is None else resolve(node.parent) @ local
            return result[index]

        return tuple(readonly(resolve(i)) for i in range(len(self.nodes)))

    def world_parts(self, translations: Mapping[str, Array] | None = None) -> tuple[Solid, ...]:
        matrices = self.matrices(translations)
        return tuple(
            Solid(
                p.node,
                p.name,
                readonly(p.triangles @ matrices[p.node][:3, :3].T + matrices[p.node][:3, 3]),
            )
            for p in self.parts
        )

    def lineage(self, index: int) -> tuple[str, ...]:
        names: list[str] = []
        current: int | None = index
        while current is not None:
            names.append(self.nodes[current].name)
            current = self.nodes[current].parent
        return tuple(names)


def components(triangles: Array, *, allow_collinear: bool = False) -> tuple[Array, ...]:
    vertices, faces = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = faces.reshape(-1, 3)
    parents = list(range(len(vertices)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for a, b, c in faces:
        owner = root(int(a))
        parents[root(int(b))] = owner
        parents[root(int(c))] = owner
    grouped: dict[int, list[int]] = {}
    for i, face in enumerate(faces):
        grouped.setdefault(root(int(face[0])), []).append(i)
    result = tuple(readonly(triangles[indices]) for indices in grouped.values())
    for solid in result:
        validate_solid(solid, allow_collinear=allow_collinear)
    return result
