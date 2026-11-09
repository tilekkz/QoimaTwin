"""Independent boxes and unchanged pinned source for conditional operator fit."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from app.v3.mesh_proof_scene import RigidNode, RigidScene, Solid
from app.v3.mesh_proof_types import Array, readonly
from app.v3.pallet_operator_fit_models import OperatorFitSource
from app.v3.pallet_operator_fit_source import load_operator_fit_source

BACKEND = Path(__file__).resolve().parents[2]
ASSETS = BACKEND / "docs/proposals/pallet-operator-fit-v1"


def source() -> OperatorFitSource:
    return load_operator_fit_source(BACKEND / "data", ASSETS)


def cube(low: tuple[float, float, float], high: tuple[float, float, float]) -> Array:
    vertices = np.array(
        [
            [x, y, z]
            for x in (low[0], high[0])
            for y in (low[1], high[1])
            for z in (low[2], high[2])
        ],
        dtype=float,
    )
    indices = [
        (0, 1, 3),
        (0, 3, 2),
        (4, 6, 7),
        (4, 7, 5),
        (0, 4, 5),
        (0, 5, 1),
        (2, 3, 7),
        (2, 7, 6),
        (0, 2, 6),
        (0, 6, 4),
        (1, 5, 7),
        (1, 7, 3),
    ]
    return readonly(vertices[np.array(indices)])


def box_scene(moving: bool = False) -> RigidScene:
    root = RigidNode("forklift_root" if moving else "body", None, readonly(np.eye(4)))
    nodes = (root, RigidNode("joint__carriage", 0, readonly(np.eye(4)))) if moving else (root,)
    part = Solid(int(moving), "box", cube((-0.1, -0.1, -0.1), (0.1, 0.1, 0.1)))
    return RigidScene("analytical", nodes, (part,))


def shifted(scene: RigidScene, name: str, offset: tuple[float, float, float]) -> RigidScene:
    nodes = []
    for node in scene.nodes:
        matrix = node.matrix.copy()
        if node.name == name:
            matrix[:3, 3] += offset
        nodes.append(replace(node, matrix=readonly(matrix)))
    return replace(scene, nodes=tuple(nodes))
