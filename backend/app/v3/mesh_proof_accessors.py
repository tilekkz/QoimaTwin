"""Bounds-checked float positions and unsigned triangle indices from a GLB."""

import numpy as np

from app.v3.mesh_proof_json import Document, entry, integer, obj, unsupported
from app.v3.mesh_proof_types import Array, MeshProofError


def accessor(document: Document, binary: bytes, index: object, positions: bool) -> Array:
    value = entry(document, "accessors", index)
    unsupported(value, ("sparse", "extensions"))
    if value.get("normalized", False) is not False:
        raise MeshProofError("normalized geometry accessor is unsupported")
    component = integer(value.get("componentType"))
    width = 3 if positions else 1
    if value.get("type") != ("VEC3" if positions else "SCALAR") or component not in (
        (5126,) if positions else (5121, 5123, 5125)
    ):
        raise MeshProofError("unsupported geometry accessor type")
    dtype = np.dtype({5126: "<f4", 5121: "u1", 5123: "<u2", 5125: "<u4"}[component])
    view = entry(document, "bufferViews", value.get("bufferView"))
    unsupported(view, ("extensions",))
    if integer(view.get("buffer")) != 0:
        raise MeshProofError("external buffer is unsupported")
    start, size = integer(view.get("byteOffset", 0)), integer(view.get("byteLength"), 1)
    offset, count = integer(value.get("byteOffset", 0)), integer(value.get("count"), 1)
    stride = integer(view.get("byteStride", width * dtype.itemsize), width * dtype.itemsize)
    end = offset + (count - 1) * stride + width * dtype.itemsize
    if end > size or start + size > len(binary) or (start + offset) % dtype.itemsize:
        raise MeshProofError("accessor bounds or alignment invalid")
    if stride % dtype.itemsize or ("byteStride" in view and (stride > 252 or stride % 4)):
        raise MeshProofError("accessor stride invalid")
    result = np.ndarray(
        (count, width),
        dtype=dtype,
        buffer=binary,
        offset=start + offset,
        strides=(stride, dtype.itemsize),
    ).astype(np.float64)
    if not np.isfinite(result).all():
        raise MeshProofError("nonfinite binary geometry")
    return result


def primitive(document: Document, binary: bytes, value: Document) -> Array:
    unsupported(value, ("targets", "extensions"))
    if value.get("mode", 4) != 4 or type(value.get("mode", 4)) is not int:
        raise MeshProofError("only TRIANGLES geometry is supported")
    attributes = obj(value.get("attributes"))
    if any(key.startswith(("JOINTS_", "WEIGHTS_")) for key in attributes):
        raise MeshProofError("skinned geometry is unsupported")
    positions = accessor(document, binary, attributes.get("POSITION"), True)
    indices = accessor(document, binary, value.get("indices"), False).ravel()
    if len(indices) % 3 or np.any(indices >= len(positions)):
        raise MeshProofError("triangle indices out of bounds")
    return positions[indices.astype(np.int64)].reshape(-1, 3, 3)
