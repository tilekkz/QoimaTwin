"""Pinned data fixtures; no scheduler, stock mutation or invented clock default."""

from pathlib import Path

import pytest

from app.v3.outbound_shift_inputs import compile_outbound_shift
from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.workload_models import WorkloadPolicy

DATA = Path(__file__).parents[2] / "data"
BASE = DATA / "v3-proposal"
ADAPTATION = DATA / "v3-adaptation-proposal"
POLICY = WorkloadPolicy(101, 3, 7, "normal")


@pytest.fixture(scope="module")
def compiled() -> OutboundShiftInputs:
    return compile_outbound_shift(BASE, ADAPTATION, POLICY)
