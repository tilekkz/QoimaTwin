"""Compact state remains typed and input-bound, including newly credited definitions."""

from dataclasses import replace
from typing import cast

import pytest

from app.v3.api_coordinator_replay_projection import project_snapshot
from app.v3.coordinator_seek import replay_coordinator
from tests.v3.test_coordinator_seek_fixtures import fresh_run


def test_receipt_state_references_only_the_actual_current_registry() -> None:
    inputs, run, _ = fresh_run("receipt")
    before = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=11_999_999)
    after = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=12_000_000)
    first = project_snapshot(inputs.profile, before)
    second = project_snapshot(inputs.profile, after)
    assert len(first["inventory"]["locations"]) == 24
    assert len(second["inventory"]["locations"]) == 48
    assert first["inventory"]["registered_receipts"] == []
    offer = inputs.profile.world.receipts.receipts[0].definition
    assert second["inventory"]["registered_receipts"] == [{"receipt_id": offer.receipt_id}]
    assert "units" not in second["inventory"]


def test_snapshot_projection_rejects_numeric_equal_scalar_alias() -> None:
    inputs, _, outcome = fresh_run("receipt")
    point = replace(outcome.at_end, tick=cast(int, True))
    with pytest.raises(ValueError):
        project_snapshot(inputs.profile, point)


def test_snapshot_projection_cannot_introduce_an_unknown_container_definition() -> None:
    inputs, _, outcome = fresh_run("receipt")
    point = outcome.at_end
    inventory = point.inventory
    forged = replace(inventory.containers[0], container_id="not-declared-in-inputs")
    point = replace(
        point,
        inventory=replace(inventory, containers=(forged, *inventory.containers[1:])),
    )
    with pytest.raises(ValueError):
        project_snapshot(inputs.profile, point)
