"""Copied rigid source joint poses; original worker geometry remains unchanged."""

import math
from dataclasses import replace
from hashlib import sha256
from typing import Any

import numpy as np

from app.v3.mesh_proof_glb import load_glb
from app.v3.mesh_proof_motion import validate_frames
from app.v3.mesh_proof_scene import RigidScene
from app.v3.mesh_proof_source import MESH_PATH
from app.v3.mesh_proof_types import CONTACT_RESIDUAL_M, Array, readonly
from app.v3.pallet_operator_fit_models import OperatorFitSource
from app.v3.pallet_operator_fit_source import WORKER_SHA256, forklift_spec
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_source import raw_document


def euler_xyz(values: list[float]) -> Array:
    x, y, z = values
    sx, sy, sz = math.sin(x), math.sin(y), math.sin(z)
    cx, cy, cz = math.cos(x), math.cos(y), math.cos(z)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=float)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=float)
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=float)
    result: Array = rx @ ry @ rz
    return result


def seated_worker(worker: RigidScene, driver: dict[str, Any]) -> RigidScene:
    require(
        driver["rotation_order"] == "native Three.js intrinsic Euler XYZ, radians",
        "Unsupported source driver rotation order",
    )
    joints = driver["jointEulerXYZ"]
    require(set(joints).issubset(n.name for n in worker.nodes), "Source worker joints absent")
    require(
        sum(n.name == "worker_base_root" for n in worker.nodes) == 1,
        "Unique source worker root required",
    )
    nodes = []
    for node in worker.nodes:
        matrix = node.matrix.copy()
        if node.name in joints:
            require(
                np.allclose(matrix[:3, :3], np.eye(3), atol=CONTACT_RESIDUAL_M, rtol=0),
                "Source joint bind rotation differs",
            )
            matrix[:3, :3] = euler_xyz(joints[node.name])
        if node.name == "worker_base_root":
            matrix[:3, 3] = driver["worker_root_translation"]
        nodes.append(replace(node, matrix=readonly(matrix)))
    return replace(worker, nodes=tuple(nodes))


def fit_scenes(source: OperatorFitSource) -> tuple[RigidScene, RigidScene]:
    worker = load_glb(source.worker_raw, WORKER_SHA256)
    raw = raw_document(source.pickup, "v3-mesh-proof-proposal", MESH_PATH)
    vehicle = load_glb(raw, sha256(raw).hexdigest(), allow_collinear=True)
    validate_frames(vehicle)
    return seated_worker(worker, forklift_spec(source)["driver"]), vehicle
