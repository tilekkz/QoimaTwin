"""Known physical storage is not permission to use an undeclared port staging buffer."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.stock_models import StockOwner
from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_run import build_whole_run
from app.v3.whole_run_inputs import freeze_hand_inputs
from app.v3.whole_transport import read_whole_run, write_whole_run
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def _substitute(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _substitute(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute(child) for child in value]
    if value == "whole-buffer":
        return "unused-buffer"
    if value == "whole:place:whole-buffer":
        return "whole:place:unused-buffer"
    return value


def test_rehashed_known_but_undeclared_buffer_cannot_bypass_port_binding(tmp_path: Path) -> None:
    profile = whole_hand_profile()
    flow = profile.receipts.flow
    flow = replace(flow, owners=(*flow.owners, StockOwner("unused-buffer", "buffer", 1)))
    buffer = next(p for p in profile.places if p.owner_id == "whole-buffer")
    profile = replace(
        profile,
        receipts=replace(profile.receipts, flow=flow),
        places=(*profile.places, replace(buffer, owner_id="unused-buffer")),
    )
    conveyor = receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 100 * SECOND, 200 * SECOND)
    outcome = WholeFlowEngine(profile, conveyor).run(100 * SECOND, 200 * SECOND)
    run = build_whole_run(inputs, outcome)
    assert run["catalog"]["whole_process"]["ports"][0]["buffer_ids"] == ["whole-buffer"]
    for key in ("events", "checkpoints", "at_horizon", "at_end"):
        run[key] = _substitute(run[key])
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        point["state_hash"] = sha256_hex(point["state"])
    with pytest.raises(ValueError):
        write_whole_run(run, tmp_path, inputs=inputs.frozen_bytes)
        read_whole_run(tmp_path)
