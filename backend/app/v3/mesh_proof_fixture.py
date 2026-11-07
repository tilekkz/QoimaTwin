"""Independent proof of the pinned local PALLET action, never a runtime grant."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from app.v3.mesh_proof_contact import contact_patch, support_margin
from app.v3.mesh_proof_motion import Segment, posed, select
from app.v3.mesh_proof_source import ACTION_PATH, MESH_PATH, Fixture, load_fixture
from app.v3.mesh_proof_sweeps import verify_segment
from app.v3.mesh_proof_types import ContactPatch

METHOD_VERSION = "qoima-local-pallet-mesh-proof-1"


@dataclass(frozen=True, slots=True)
class ContactEvidence:
    pose_index: int
    support: str
    patch: ContactPatch
    combined_support_margin_m: float


@dataclass(frozen=True, slots=True)
class SegmentEvidence:
    ordinal: int
    phase: str
    covers_checked: int
    motion: Segment


@dataclass(frozen=True, slots=True)
class LocalGeometryProof:
    method_version: str
    scope: str
    mesh_sha256: str
    action_sha256: str
    bindings: tuple[tuple[str, str], ...]
    segments: tuple[SegmentEvidence, ...]
    contacts: tuple[ContactEvidence, ...]
    assumptions: tuple[str, ...]
    solid_count: int
    triangle_count: int
    collinear_triangle_count: int
    same_hu: bool = True
    operational_admission: Literal[False] = False


def _contacts(fixture: Fixture) -> tuple[ContactEvidence, ...]:
    scene = fixture.scene
    result: list[ContactEvidence] = []
    for index in (3, 4, 7, 9, 10):
        pose = fixture.segments[index].start
        parts = posed(scene, pose, True)
        cargo = tuple(p.triangles for p in select(scene, parts, "pallet-load__HU"))
        patches: list[ContactPatch] = []
        for side in ("L", "R"):
            support = select(scene, parts, f"joint__fork_{side}")
            patch = contact_patch(tuple(p.triangles for p in support), cargo, pose.fork_top)
            patches.append(patch)
        margin = support_margin(patches, (0.0, pose.root_z + 1 + pose.reach))
        result.extend(
            ContactEvidence(index, "fork_" + side, patch, margin)
            for side, patch in zip(("L", "R"), patches, strict=True)
        )
    for index in (0, 10, 13):
        pose = fixture.segments[index].start if index < 13 else fixture.segments[-1].end
        parts = posed(scene, pose, False)
        platform = tuple(p.triangles for p in select(scene, parts, "heavy-bay__MODULE"))
        cargo = tuple(p.triangles for p in select(scene, parts, "pallet-load__HU"))
        patch = contact_patch(platform, cargo, 0.18)
        result.append(
            ContactEvidence(index, "platform", patch, support_margin((patch,), (0.0, 1.4)))
        )
    return tuple(result)


def verify_repository_pallet_fixture(root: Path) -> LocalGeometryProof:
    fixture = load_fixture(root)
    bounds = np.array([-0.8, 0.0, -2.55]), np.array([0.8, 2.1, 2.2])
    evidence = tuple(
        SegmentEvidence(
            segment.ordinal, segment.phase, verify_segment(fixture.scene, segment, bounds), segment
        )
        for segment in fixture.segments
    )
    hashes = dict(fixture.hashes)
    triangles = np.concatenate([part.triangles for part in fixture.scene.parts])
    collinear = int(
        np.count_nonzero(
            np.all(
                np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]) == 0,
                axis=1,
            )
        )
    )
    assumptions = (
        "Fixed yaw; piecewise affine translations; wheel full-radial envelopes.",
        "Quasi-static vertical gravity at declared CoG; no dynamic/material strength proof.",
        "Open cover inset 3e-7m; contact/frame residual <=2e-6m; area floor 1e-12m2.",
        "Exact collinear triangles retain collision cover and contribute zero surface area.",
        "Isolated fixture only; no warehouse occupancy, driver, timing or IN_W grant.",
        "Vehicle/HU-platform and HU-vehicle checks; mechanical self-contacts are outside scope.",
    )
    return LocalGeometryProof(
        METHOD_VERSION,
        "isolated_fixed_yaw_pallet_fixture",
        hashes[MESH_PATH],
        hashes[ACTION_PATH],
        fixture.hashes,
        evidence,
        _contacts(fixture),
        assumptions,
        len(fixture.scene.parts),
        len(triangles),
        collinear,
    )
