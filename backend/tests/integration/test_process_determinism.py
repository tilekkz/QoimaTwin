"""Independent process/hash-seed check; versioned fixed golden is added after export integration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _process(seed: str, *, optimized: bool = False) -> dict[str, str]:
    command = [sys.executable, *(["-O"] if optimized else []), "-m", "tests.probes", "--fixture"]
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    data = json.loads(result.stdout)
    assert isinstance(data, dict)
    return {str(k): str(v) for k, v in data.items()}


def test_fixture_process_is_independent_of_hash_seed_and_optimization() -> None:
    first = _process("1")
    assert first == _process("271828", optimized=True)
    assert set(first) == {"run_id", "events_sha256"}
    assert all(len(value) == 64 for value in first.values())
