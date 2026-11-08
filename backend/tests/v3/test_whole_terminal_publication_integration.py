"""Actual corrected runtime output must pass the corrected strict whole publisher."""

import pytest

from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_run import build_whole_run
from app.v3.whole_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_terminal_capacity import mixed_terminal_profile


@pytest.mark.parametrize("capacity", [1, 2])
def test_actual_runtime_and_strict_publisher_agree_on_shared_terminal_capacity(
    capacity: int,
) -> None:
    profile, conveyor = mixed_terminal_profile(capacity), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 181 * SECOND, 220 * SECOND)
    outcome = WholeFlowEngine(profile, conveyor).run(181 * SECOND, 220 * SECOND)
    run = build_whole_run(inputs, outcome)
    state = run["at_end"]["state"]
    assert state["orders"][0]["shipped_tick"] == 192_170_000
    assert len(state["stock"]["locations"]) == 48  # Initial24 plus actual receipt24.
    owners = {row["container_id"]: row["owner_id"] for row in state["stock"]["containers"]}
    assert owners["P1"] == "shipped"
    whole = state["whole_orders"][0]
    if capacity == 1:
        for point in (run["at_horizon"], run["at_end"]):
            waiting = point["state"]["whole_orders"][0]
            assert waiting["port_reserved_tick"] is None and waiting["shipped_tick"] is None
            assert waiting["wait_reason"] == "shipped_capacity"
        assert owners["HU2"] == "whole-buffer" and run["status"] == "partial"
    else:
        assert whole["port_reserved_tick"] == 180 * SECOND
        assert whole["service_started_tick"] == 185 * SECOND
        assert whole["shipped_tick"] == 210 * SECOND
        assert whole["returned_tick"] == 215 * SECOND
        assert owners["HU2"] == "shipped" and run["status"] == "complete"
        assert state["leases"] == []
