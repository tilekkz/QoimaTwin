"""Two sequential actual engines, frozen input evidence first, strict native readback last."""

from pathlib import Path
from typing import Any

from app.errors import OutputNotEmptyError, require_empty_output
from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_run_inputs import load_run_inputs as load_common
from app.v3.coordinator_transport_files import put
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_pair_inputs import PreparedRelocationPair, verify_relocation_pair
from app.v3.relocation_pair_report import build_pair_report
from app.v3.relocation_run import build_relocation_run
from app.v3.relocation_transport import read_relocation_run, write_relocation_run


def execute_relocation_pair(pair: PreparedRelocationPair, out_dir: Path) -> dict[str, Any]:
    prepared = verify_relocation_pair(pair)
    common = load_common(prepared.baseline.common_inputs)
    _, conveyor, _ = _pinned_reference()
    _freeze(prepared, out_dir)
    before = RelocationEngine(prepared.baseline.profile, conveyor).run(
        common.horizon_tick, common.end_tick
    )
    after = RelocationEngine(prepared.candidate.profile, conveyor).run(
        common.horizon_tick, common.end_tick
    )
    left = build_relocation_run(prepared.baseline, before)
    right = build_relocation_run(prepared.candidate, after)
    left = _publish(left, out_dir / "baseline", prepared.baseline.frozen_bytes)
    right = _publish(right, out_dir / "candidate", prepared.candidate.frozen_bytes)
    report = build_pair_report(prepared, left, right, before, after)
    put(out_dir, "comparison.json", canonical_bytes(report))
    return report


def _freeze(pair: PreparedRelocationPair, out_dir: Path) -> None:
    if out_dir.is_symlink():
        raise OutputNotEmptyError("Relocation pair output must not be a symbolic link")
    require_empty_output(out_dir)
    put(out_dir, "inputs.json", pair.frozen_bytes)
    put(out_dir, "baseline/inputs.json", pair.baseline.frozen_bytes)
    put(out_dir, "candidate/inputs.json", pair.candidate.frozen_bytes)


def _publish(run: dict[str, Any], root: Path, inputs: bytes) -> dict[str, Any]:
    write_relocation_run(run, root, inputs=inputs)
    restored = read_relocation_run(root)
    if canonical_bytes(restored) != canonical_bytes(run):
        raise ValueError("Relocation strict readback differs from its actual observed run")
    return restored
