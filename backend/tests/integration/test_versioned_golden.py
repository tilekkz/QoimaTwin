"""The same fixed fixture identity and event signature must hold on each CI platform."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("seed,optimized", [("1", False), ("271828", True)])
def test_versioned_fixture_golden_in_fresh_process(seed: str, optimized: bool) -> None:
    result = subprocess.run(
        [sys.executable, *(["-O"] if optimized else []), "-m", "tests.golden_probe"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    checked = json.loads(result.stdout)
    assert checked["status"] == "passed"
    assert checked["engine_version"] == "qoima-engine-0.4.0"
    assert checked["identity_version"] == "qoima-run-v2"
