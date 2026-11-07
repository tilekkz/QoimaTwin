"""Closed solid checks and conservative continuous translation covers."""

from collections import Counter
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from app.v3.mesh_proof_types import SURFACE_INSET_M, Array, MeshProofError

NDArrayBool = NDArray[np.bool_]


def validate_solid(triangles: Array, *, allow_collinear: bool = False) -> None:
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3):
        raise MeshProofError("triangle shape must be (n,3,3)")
    if not len(triangles) or not np.isfinite(triangles).all():
        raise MeshProofError("empty or nonfinite solid")
    _, faces = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = faces.reshape(-1, 3)
    directed: Counter[tuple[int, int]] = Counter()
    for face in faces:
        for i in range(3):
            directed[int(face[i]), int(face[(i + 1) % 3])] += 1
    if any(a == b or count != 1 or directed[b, a] != 1 for (a, b), count in directed.items()):
        raise MeshProofError("solid is not closed with consistent winding")
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = np.linalg.norm(normals, axis=1)
    if np.any((areas <= 2e-13) & ((areas != 0) | (not allow_collinear))):
        raise MeshProofError("degenerate triangle")
    volume = np.einsum("ij,ij->", triangles[:, 0], normals) / 6
    if not np.isfinite(volume) or volume <= 1e-12:
        raise MeshProofError("solid has nonpositive signed volume")


def _intersections(triangles: Array, low: Array, high: Array) -> NDArrayBool:
    points = triangles - (low + high) / 2
    edges = np.roll(points, -1, axis=1) - points
    units = np.broadcast_to(np.eye(3), (len(points), 3, 3))
    cross_axes = np.cross(edges[:, :, None, :], np.eye(3)[None, None, :, :])
    axes = np.concatenate(
        (units, np.cross(edges[:, 0], edges[:, 1])[:, None, :], cross_axes.reshape(-1, 9, 3)),
        axis=1,
    )
    projection = np.einsum("nvi,nai->nva", points, axes)
    radius = np.einsum("nai,i->na", np.abs(axes), (high - low) / 2)
    separates = (projection.min(axis=1) > radius + 1e-12) | (
        projection.max(axis=1) < -radius - 1e-12
    )
    separates &= np.einsum("nai,nai->na", axes, axes) >= 1e-22
    return np.asarray(~separates.any(axis=1), dtype=np.bool_)


def triangle_box(triangle: Array, low: Array, high: Array) -> bool:
    return bool(_intersections(triangle[None, :, :], low, high)[0])


def inside_solid(triangles: Array, point: Array) -> bool:
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    triangles = triangles[np.any(normals != 0, axis=1)]
    vectors = triangles - point
    lengths = np.linalg.norm(vectors, axis=2)
    if np.any(lengths <= 1e-14):
        raise MeshProofError("ambiguous point on a solid vertex")
    a, b, c = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
    denominator = lengths.prod(axis=1)
    denominator += np.einsum("ij,ij->i", a, b) * lengths[:, 2]
    denominator += np.einsum("ij,ij->i", b, c) * lengths[:, 0]
    denominator += np.einsum("ij,ij->i", c, a) * lengths[:, 1]
    winding = float(np.sum(2 * np.arctan2(numerator, denominator)))
    if min(abs(winding), abs(abs(winding) - 4 * np.pi)) > 1e-6:
        raise MeshProofError("ambiguous solid winding")
    return abs(winding) > 2 * np.pi


def empty_box(solids: Sequence[Array], low: Array, high: Array) -> None:
    if not np.isfinite([low, high]).all() or np.any(high - low <= 2 * SURFACE_INSET_M):
        raise MeshProofError("invalid or sub-resolution cover")
    inner_low, inner_high = low + SURFACE_INSET_M, high - SURFACE_INSET_M
    for solid in solids:
        if np.any(solid.max(axis=(0, 1)) <= inner_low) or np.any(
            solid.min(axis=(0, 1)) >= inner_high
        ):
            continue
        candidates = solid[
            (solid.max(axis=1) > inner_low).all(axis=1)
            & (solid.min(axis=1) < inner_high).all(axis=1)
        ]
        if len(candidates) and _intersections(candidates, inner_low, inner_high).any():
            raise MeshProofError("triangle intrusion into continuous cover")
        if inside_solid(solid, (low + high) / 2):
            raise MeshProofError("cover is inside a closed solid")
