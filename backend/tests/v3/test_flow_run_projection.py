"""Captured state is actual settled state, with immutable recipes separated from checkpoints."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.flow_run import build_flow_run, validate_flow_run
from app.v3.flow_run_values import checkpoint
from tests.v3.test_flow_run_fixtures import sample


def test_projection_preserves_hand_horizon_end_and_mutable_only_stock() -> None:
    inputs, outcome = sample()
    run = build_flow_run(inputs, outcome)
    assert run["at_horizon"] == checkpoint(outcome.at_horizon)
    assert run["at_end"] == checkpoint(outcome.at_end)
    assert run["at_end"]["tick"] == 197_170_000
    assert run["metrics"]["at_end"]["completed_units"] == 3
    assert run["metrics"]["at_horizon"]["completed_units"] == 0
    assert run["capabilities"]["arbitrary_seek"] is False
    for row in run["checkpoints"]:
        assert row["last_seq"] == max(
            (e.seq for e in outcome.events if e.tick <= row["tick"]), default=-1
        )
        assert all(
            set(c) == {"container_id", "owner_id", "sealed_for"}
            for c in row["state"]["stock"]["containers"]
        )
        assert "events" not in row["state"] and "history" not in row["state"]


@pytest.mark.parametrize("defect", ["run_id", "seq", "watermark", "future", "recipe"])
def test_semantic_corruption_is_rejected(defect: str) -> None:
    run = deepcopy(build_flow_run(*sample()))
    if defect == "run_id":
        run["run_id"] = "0" * 64
    elif defect == "seq":
        run["events"][0]["seq"] = 5
    elif defect == "watermark":
        run["checkpoints"][0]["last_seq"] = 999
    elif defect == "future":
        run["events"][-1]["tick"] = 300_000_000
    else:
        run["checkpoints"][0]["state"]["stock"]["containers"][0]["recipe"] = {}
    with pytest.raises(ValueError):
        validate_flow_run(run)


def test_open_belt_motion_cannot_already_be_completed_at_captured_tick() -> None:
    run = deepcopy(build_flow_run(*sample(True)))
    row = run["checkpoints"][-1]
    motion = row["state"]["belt"]["carriers"][0]["motion"]
    assert motion is not None
    motion["planned_end_tick"] = row["tick"]
    row["state_hash"] = sha256_hex(row["state"])
    run["at_horizon"] = run["at_end"] = deepcopy(row)
    with pytest.raises(ValueError, match="motion"):
        validate_flow_run(run)
