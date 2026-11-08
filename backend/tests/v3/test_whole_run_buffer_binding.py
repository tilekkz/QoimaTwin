"""An admitted whole job cannot switch even between two permitted finite buffers."""

from dataclasses import replace

import pytest

from app.v3.stock_models import StockOwner
from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_run import build_whole_run, validate_whole_run
from app.v3.whole_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def test_transient_whole_view_cannot_switch_its_admitted_permitted_buffer() -> None:
    profile = whole_hand_profile()
    flow = profile.receipts.flow
    flow = replace(flow, owners=(*flow.owners, StockOwner("z-buffer", "buffer", 1)))
    buffer = next(p for p in profile.places if p.owner_id == "whole-buffer")
    profile = replace(
        profile,
        receipts=replace(profile.receipts, flow=flow),
        places=(*profile.places, replace(buffer, owner_id="z-buffer")),
        ports=(replace(profile.ports[0], buffer_ids=("whole-buffer", "z-buffer")),),
    )
    conveyor = receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 100 * SECOND, 200 * SECOND)
    outcome = WholeFlowEngine(profile, conveyor).run(100 * SECOND, 200 * SECOND)
    run = build_whole_run(inputs, outcome)
    changed = next(e for e in run["events"] if e["kind"] == "whole_state_changed")
    changed["whole_order"]["buffer_owner_id"] = "z-buffer"
    with pytest.raises(ValueError, match=r"buffer|assignment"):
        validate_whole_run(run)
