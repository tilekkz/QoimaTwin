"""Conservative covers of complete triangles and full wheel revolutions."""

from dataclasses import dataclass

import numpy as np

from app.v3.mesh_proof_motion import Pose, translations
from app.v3.mesh_proof_scene import RigidScene, Solid
from app.v3.mesh_proof_types import CONTACT_RESIDUAL_M, Array, MeshProofError


@dataclass(frozen=True, slots=True)
class Cover:
    name: str
    low: Array
    high: Array
    triangle_indices: tuple[int, ...] = ()


def _fork_covers(part: Solid, pose: Pose) -> tuple[Cover, ...]:
    triangles = part.triangles
    blade = (triangles[:, :, 1] <= pose.fork_top + CONTACT_RESIDUAL_M).all(axis=1)
    heel = (triangles[:, :, 2] <= pose.root_z + 0.4 + pose.reach + CONTACT_RESIDUAL_M).all(axis=1)
    corner = ~(blade | heel)
    return tuple(
        Cover(
            part.name + suffix,
            triangles[mask].min(axis=(0, 1)),
            triangles[mask].max(axis=(0, 1)),
            tuple(int(i) for i in np.flatnonzero(mask)),
        )
        for suffix, mask in ((":blade", blade), (":heel", heel), (":corner", corner))
        if mask.any()
    )


def covers(scene: RigidScene, parts: tuple[Solid, ...], pose: Pose) -> tuple[Cover, ...]:
    matrices = scene.matrices(translations(pose, False))
    node_index = {node.name: index for index, node in enumerate(scene.nodes)}
    result: list[Cover] = []
    for part in parts:
        lineage = scene.lineage(part.node)
        wheel = next((name for name in lineage if name.startswith("joint__wheel_")), None)
        low, high = part.triangles.min(axis=(0, 1)), part.triangles.max(axis=(0, 1))
        if wheel is not None:
            matrix = matrices[node_index[wheel]]
            if not np.allclose(matrix[:3, :3], np.eye(3), rtol=0, atol=1e-12):
                raise MeshProofError("wheel rotation axis is not supported")
            centre = matrix[:3, 3]
            radius = np.linalg.norm(part.triangles[:, :, 1:] - centre[1:], axis=2).max()
            low[1:], high[1:] = centre[1:] - radius, centre[1:] + radius
            result.append(Cover(part.name, low, high))
        elif any(name in lineage for name in ("joint__fork_L", "joint__fork_R")):
            result.extend(_fork_covers(part, pose))
        else:
            result.append(Cover(part.name, low, high))
    return tuple(result)


def merge_covers(first: tuple[Cover, ...], second: tuple[Cover, ...]) -> tuple[Cover, ...]:
    if [c.name for c in first] != [c.name for c in second]:
        raise MeshProofError("moving geometry changed identity")
    if any(a.triangle_indices != b.triangle_indices for a, b in zip(first, second, strict=True)):
        raise MeshProofError("cover triangle membership changed")
    return tuple(
        Cover(a.name, np.minimum(a.low, b.low), np.maximum(a.high, b.high), a.triangle_indices)
        for a, b in zip(first, second, strict=True)
    )
