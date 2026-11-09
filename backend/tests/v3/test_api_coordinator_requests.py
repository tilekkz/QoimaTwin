"""Prewritten strict public API choices; checks are deferred until final integration."""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.v3.api_coordinator_identity import public_run_id
from app.v3.api_coordinator_inputs import PROFILE, CoordinatorRequest
from app.v3.api_whole_identity import public_run_id as whole_public_id
from app.v3.input_pin import LAYOUT_VERSION, SOURCE_REVISION


@pytest.mark.parametrize("override", ["profile_path", "orders", "role_intents", "horizon_tick"])
def test_public_request_cannot_override_registered_source_or_physics(override: str) -> None:
    value: dict[str, Any] = {
        "profile": PROFILE,
        "layout_version": LAYOUT_VERSION,
        "source_revision": SOURCE_REVISION,
        override: "caller-supplied",
    }
    with pytest.raises(ValidationError):
        CoordinatorRequest.from_data(value)


def test_public_identity_has_its_own_domain_and_exact_bundle_binding() -> None:
    native, bundle = "a" * 64, "b" * 64
    assert public_run_id(native, bundle) != whole_public_id(native, bundle)
    assert public_run_id(native, bundle) != public_run_id(native, "c" * 64)


def test_hand_fixture_name_is_not_a_public_source_profile() -> None:
    with pytest.raises(ValidationError):
        CoordinatorRequest.from_data(
            {
                "profile": "hand-staff-v1",
                "layout_version": LAYOUT_VERSION,
                "source_revision": SOURCE_REVISION,
            }
        )


def test_direct_coordinator_input_import_has_no_api_initialization_cycle() -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.v3.api_coordinator_inputs; from app.api import create_app",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
