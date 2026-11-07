"""Finite horizontal contact polygons from actual triangles, not ray samples."""

from collections.abc import Sequence

import numpy as np

from app.v3.mesh_proof_types import (
    CONTACT_RESIDUAL_M,
    MIN_CONTACT_AREA_M2,
    Array,
    ContactPatch,
    MeshProofError,
)


def _cross(a: Array, b: Array) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _clip(subject: Array, clip: Array) -> Array:
    polygon = list(subject)
    area = sum(_cross(a, b) for a, b in zip(clip, np.roll(clip, -1, axis=0), strict=True))
    if area < 0:
        clip = clip[::-1]
    for a, b in zip(clip, np.roll(clip, -1, axis=0), strict=True):
        result: list[Array] = []
        for p, q in zip(polygon, polygon[1:] + polygon[:1], strict=True):
            dp, dq = _cross(b - a, p - a), _cross(b - a, q - a)
            if dp >= 0:
                result.append(p)
            if (dp >= 0) != (dq >= 0):
                result.append(p + (q - p) * dp / (dp - dq))
        polygon = result
        if not polygon:
            break
    return np.asarray(polygon, dtype=np.float64).reshape(-1, 2)


def _area_centroid(polygon: Array) -> tuple[float, Array]:
    if len(polygon) < 3:
        return 0.0, np.zeros(2)
    after = np.roll(polygon, -1, axis=0)
    cross = polygon[:, 0] * after[:, 1] - after[:, 0] * polygon[:, 1]
    signed = float(cross.sum()) / 2
    if abs(signed) <= MIN_CONTACT_AREA_M2:
        return 0.0, np.zeros(2)
    centroid = ((polygon + after) * cross[:, None]).sum(axis=0) / (6 * signed)
    return abs(signed), centroid


def _bounds_overlap(first: Array, second: Array) -> bool:
    return bool(
        np.all(first.max(axis=0) > second.min(axis=0))
        and np.all(second.max(axis=0) > first.min(axis=0))
    )


def _faces(solids: Sequence[Array], plane: float, direction: int) -> Array:
    triangles = np.concatenate(solids)
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    length = np.linalg.norm(normal, axis=1)
    horizontal = normal[:, 1] * direction >= length * (1 - 1e-12)
    matching = np.max(np.abs(triangles[:, :, 1] - plane), axis=1) <= CONTACT_RESIDUAL_M
    return triangles[horizontal & matching & (length > 1e-13)]


def contact_patch(support: Sequence[Array], cargo: Sequence[Array], plane: float) -> ContactPatch:
    top, bottom = _faces(support, plane, 1), _faces(cargo, plane, -1)
    total, weighted, gap = 0.0, np.zeros(2), 0.0
    vertices: list[tuple[float, float]] = []
    polygons: list[Array] = []
    for upper in top:
        for lower in bottom:
            if not _bounds_overlap(upper[:, (0, 2)], lower[:, (0, 2)]):
                continue
            polygon = _clip(upper[:, (0, 2)], lower[:, (0, 2)])
            area, centroid = _area_centroid(polygon)
            if area > 0:
                if any(
                    _bounds_overlap(polygon, old)
                    and _area_centroid(_clip(polygon, old))[0] > MIN_CONTACT_AREA_M2
                    for old in polygons
                ):
                    raise MeshProofError("overlapping contact patches are unsupported")
                polygons.append(polygon)
                total += area
                weighted += area * centroid
                gap = max(gap, float(np.abs(upper[:, 1, None] - lower[:, 1]).max()))
                vertices.extend((float(p[0]), float(p[1])) for p in polygon)
    if total <= MIN_CONTACT_AREA_M2 or gap > CONTACT_RESIDUAL_M:
        raise MeshProofError("no finite matching contact area")
    return ContactPatch(
        total,
        (float(weighted[0] / total), float(weighted[1] / total)),
        tuple(sorted(set(vertices))),
        gap,
    )


def _convex_hull(points: tuple[tuple[float, float], ...]) -> Array:
    ordered = sorted(set(points))
    halves: list[list[Array]] = []
    for order in (ordered, ordered[::-1]):
        half: list[Array] = []
        for point in order:
            value = np.array(point)
            while len(half) > 1 and _cross(half[-1] - half[-2], value - half[-1]) <= 0:
                half.pop()
            half.append(value)
        halves.append(half[:-1])
    return np.array(halves[0] + halves[1])


def support_margin(patches: Sequence[ContactPatch], cog_xz: tuple[float, float]) -> float:
    hull = _convex_hull(tuple(point for patch in patches for point in patch.vertices_xz))
    if len(hull) < 3:
        raise MeshProofError("CoG has no finite support polygon")
    point = np.array(cog_xz)
    distances = [
        _cross(b - a, point - a) / float(np.linalg.norm(b - a))
        for a, b in zip(hull, np.roll(hull, -1, axis=0), strict=True)
    ]
    margin = min(distances)
    if not np.isfinite(margin) or margin <= 1e-9:
        raise MeshProofError("CoG is outside or on the support boundary")
    return margin
