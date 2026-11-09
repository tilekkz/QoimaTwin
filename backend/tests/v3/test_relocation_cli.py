"""The standalone CLI executes an analytical no-op pair in an actual child process."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from app.v3.relocation_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def test_standalone_compare_command_publishes_two_native_noop_runs(tmp_path: Path) -> None:
    profile = replace(relocation_hand(), jobs=())
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), SECOND, 2 * SECOND)
    baseline, candidate = tmp_path / "baseline.json", tmp_path / "candidate.json"
    baseline.write_bytes(inputs.frozen_bytes)
    candidate.write_bytes(inputs.frozen_bytes)
    output = tmp_path / "comparison"
    command = [
        sys.executable,
        "-m",
        "app.v3.relocation_cli",
        "compare",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--out",
        str(output),
    ]
    process = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert process.returncode == 0, process.stderr + process.stdout
    summary = json.loads(process.stdout)
    assert summary["status"] == "complete" and summary["no_op"] is True
    assert summary["net_paid_ticks"] == {"at_horizon": 0, "at_end": 0}
    report = json.loads((output / "comparison.json").read_bytes())
    assert report["executions"] == 2
    assert report["baseline"]["event_sha256"] == report["candidate"]["event_sha256"]
    assert (output / "baseline/manifest.json").is_file()
    assert (output / "candidate/manifest.json").is_file()
