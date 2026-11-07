"""Types and declared numerical policy for isolated rigid-mesh proofs."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]
SURFACE_INSET_M = 3e-7
CONTACT_RESIDUAL_M = 2e-6
MIN_CONTACT_AREA_M2 = 1e-12


class MeshProofError(ValueError):
    """The supplied geometry cannot satisfy the supported proof obligations."""


@dataclass(frozen=True, slots=True)
class ContactPatch:
    area_m2: float
    centroid_xz: tuple[float, float]
    vertices_xz: tuple[tuple[float, float], ...]
    maximum_gap_m: float


def readonly(values: Array) -> Array:
    payload = np.asarray(values, dtype=np.float64).tobytes()
    result: Array = np.frombuffer(payload, dtype=np.float64).reshape(values.shape)
    return result
