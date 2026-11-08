"""Explicit hand rates and fresh source proof for independent local-cycle checks."""

from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_engine import PalletCycleEngine
from app.v3.pallet_cycle_proof import certified_geometry
from app.v3.pallet_cycle_types import CycleJob, CycleTimingProfile, PhysicalPallet

ROOT = Path(__file__).resolve().parents[2] / "data"
PROOF_ROOT = ROOT / "v3-mesh-proof-proposal"
HU_ID = "independent-physical-PALLET"
ARC = "v3:module:HEAVY_E:001:B1:vehicle:segment:002:"


@pytest.fixture(name="independent_proof", scope="session")
def independent_proof_fixture() -> LocalGeometryProof:
    return certified_geometry(PROOF_ROOT)


def hand_profile() -> CycleTimingProfile:
    return CycleTimingProfile(
        "independent-hand",
        F(1),
        F(13, 25),
        F(2, 5),
        F(1, 5),
        F(3, 10),
        F(1),
        "Synthetic hand oracle: 4.2m root + 2.08m lift + 1.6m reach + 1.5s handling",
    )


def request(name: str, ready: int = 0) -> CycleJob:
    return CycleJob(name, ready, HU_ID)


def physical(proof: LocalGeometryProof) -> PhysicalPallet:
    return PhysicalPallet(HU_ID, "PALLET_LOAD", 24, F(455), proof.mesh_sha256)


def new_engine(
    proof: LocalGeometryProof, jobs: tuple[CycleJob, ...], *, bridge: bool = False
) -> PalletCycleEngine:
    return PalletCycleEngine(
        hand_profile(), jobs, physical(proof), PROOF_ROOT, proof, source_approach=bridge
    )
