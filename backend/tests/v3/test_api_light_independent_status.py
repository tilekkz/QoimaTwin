"""Actual complete artifacts cannot retain active operations hidden by empty order IDs."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import sha256_hex
from app.v3.api_light_worker import publish_output
from app.v3.flow_transport import write_flow_run
from tests.v3.test_flow_export_independent_semantics import hand_run
from tests.v3.test_flow_run_fixtures import sample


def forged_end(run: dict[str, Any], kind: str) -> None:
    point = next(c for c in run["checkpoints"] if c["tick"] == run["observed_until_tick"])
    state, tick = point["state"], point["tick"]
    worker = next(w for w in state["workers"] if w["actor_id"] == "P01")
    assert worker["order_id"] is None and state["cart"]["order_id"] is None
    if kind == "worker_waiting":
        worker["waiting_since"] = tick
    elif kind == "belt_motion":
        motion = deepcopy(
            next(
                c["motion"]
                for p in run["checkpoints"]
                for c in p["state"]["belt"]["carriers"]
                if c["motion"] is not None
            )
        )
        duration = motion["planned_end_tick"] - motion["start_tick"]
        motion.update(start_tick=tick, planned_end_tick=tick + duration)
        carrier = state["belt"]["carriers"][0]
        assert carrier["status"] == "complete"
        carrier["motion"] = motion
    else:
        operation = deepcopy(
            next(e["operation"] for e in run["events"] if e["actor_id"] == "P01" and e["operation"])
        )
        duration = operation["planned_end_tick"] - operation["start_tick"]
        operation.update(start_tick=tick, planned_end_tick=tick + duration)
        target = state["cart"] if kind == "cart_operation" else worker
        target["operation"] = operation
    point["state_hash"] = sha256_hex(state)
    run["at_end"] = deepcopy(point)


@pytest.mark.parametrize(
    "kind", ["worker_operation", "worker_waiting", "cart_operation", "belt_motion"]
)
def test_complete_publication_rejects_active_resources_in_rehashed_native_artifact(
    tmp_path: Path, kind: str
) -> None:
    inputs, _ = sample()
    run = deepcopy(hand_run())
    assert run["status"] == "complete"
    forged_end(run, kind)
    with pytest.raises(ValueError):
        write_flow_run(run, tmp_path / "run", inputs=inputs.frozen_bytes)
        result = publish_output(
            ArtifactStore(tmp_path / "store"),
            "b" * 64,
            tmp_path / "run",
            {"input_hash": inputs.input_hash},
        )
        assert result["status"] == "complete"
