"""Source-bound target suffix with actual recomputed loaded connector proof on invocation."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Literal

import numpy as np

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_sources import _same_types
from app.v3.flow_profile_wire import record
from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.mesh_proof_motion import Pose, Segment
from app.v3.mesh_proof_source import load_fixture
from app.v3.mesh_proof_sweeps import verify_segment
from app.v3.pallet_cycle_bridge import build_bridges
from app.v3.pallet_cycle_plan import build_cycle_plan
from app.v3.pallet_cycle_proof import validate_proof
from app.v3.pallet_cycle_types import CycleBridge, CycleOperation, CycleTimingProfile, ExactPose
from app.v3.pallet_receipt_types import PalletReceiptError, PutawayPrimitive


def compile_putaway_primitive(
    proof_root: Path,
    proof: LocalGeometryProof,
    timing: CycleTimingProfile,
    *,
    source_bridge: bool,
) -> PutawayPrimitive:
    if type(source_bridge) is not bool or type(timing) is not CycleTimingProfile:
        raise PalletReceiptError("TYPED_PUTAWAY_CHOICES_REQUIRED", "exact timing and bridge choice")
    certified = validate_proof(proof_root, proof)
    plan = build_cycle_plan(proof_root, timing)
    suffix = _suffix(plan)
    bridge, checks = None, 0
    if source_bridge:
        suffix, bridge, checks = _connect(proof_root, timing, suffix)
    elapsed, release = 0, None
    for op in suffix:
        elapsed += op.duration_ticks
        if op.kind == "release":
            release = elapsed
    if release is None:
        raise PalletReceiptError("PUTAWAY_RELEASE_MISSING", "proved suffix has no handoff")
    binding: Literal["local_fixture_only", "source_prehandle_bound"] = (
        "source_prehandle_bound" if source_bridge else "local_fixture_only"
    )
    return PutawayPrimitive(
        suffix,
        release,
        elapsed,
        certified.bindings,
        checks,
        bridge,
        certified.method_version,
        binding,
    )


def verify_putaway_primitive(
    proof_root: Path,
    proof: LocalGeometryProof,
    timing: CycleTimingProfile,
    value: PutawayPrimitive,
    *,
    source_bridge: bool,
) -> None:
    expected = compile_putaway_primitive(proof_root, proof, timing, source_bridge=source_bridge)
    if not _same_types(value, expected) or canonical_bytes(record(value)) != canonical_bytes(
        record(expected)
    ):
        raise PalletReceiptError("PUTAWAY_PRIMITIVE_CHANGED", "actual proved primitive differs")


def _suffix(plan: tuple[CycleOperation, ...]) -> tuple[CycleOperation, ...]:
    starts = [i for i, op in enumerate(plan) if op.phase == "travel_approach"]
    if len(starts) != 1:
        raise PalletReceiptError("PUTAWAY_SUFFIX_UNKNOWN", "unique source loaded approach required")
    result = plan[starts[0] :]
    expected = ExactPose(Fraction("-1.05"), Fraction(".7"), Fraction(0))
    if (
        result[0].start_pose != expected
        or result[0].attached is not True
        or result[-1].end_pose != expected
        or result[-1].attached is not False
        or any(op.kind == "attach" for op in result)
        or sum(op.kind == "release" for op in result) != 1
    ):
        raise PalletReceiptError(
            "PUTAWAY_PRECONDITION_MISMATCH", "already-loaded local suffix required"
        )
    return tuple(replace(op, ordinal=i) for i, op in enumerate(result))


def _connect(
    root: Path,
    timing: CycleTimingProfile,
    suffix: tuple[CycleOperation, ...],
) -> tuple[tuple[CycleOperation, ...], CycleBridge, int]:
    data = Path(__file__).resolve().parents[2] / "data"
    entry, exit_op, bridge = build_bridges(
        root, timing, suffix[0].start_pose, data / "v3-proposal", data / "v3-vehicle-proposal"
    )
    loaded_entry = replace(entry, attached=True, phase="loaded_source_approach")
    scene = load_fixture(root).scene
    start, end = loaded_entry.start_pose, loaded_entry.end_pose
    segment = Segment(
        0,
        loaded_entry.phase,
        Pose(float(start.root_z), float(start.fork_top), float(start.reach)),
        Pose(float(end.root_z), float(end.fork_top), float(end.reach)),
        True,
    )
    bounds = np.array([-0.8, 0.0, -2.55]), np.array([0.8, 2.1, 2.2])
    checks = verify_segment(scene, segment, bounds)
    if checks <= 0:
        raise PalletReceiptError("LOADED_BRIDGE_PROOF_EMPTY", "actual continuous coverage required")
    combined = (loaded_entry, *suffix, exit_op)
    return (
        tuple(replace(op, ordinal=i) for i, op in enumerate(combined)),
        replace(bridge, entry_cover_checks=checks),
        checks,
    )
