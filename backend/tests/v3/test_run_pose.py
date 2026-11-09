"""Rendering anchors use actual augmented graph geometry and observed time only."""

import pytest

from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run
from app.v3.run_pose import actor_pose_at, hu_location_at
from tests.v3.test_run_fixtures import manual_profile


def test_clipped_carry_uses_declared_graph_segment_without_future_position() -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(15_000_000, 18_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=18_000_000
    )
    pose = actor_pose_at(run, "R01", 18_000_000)
    # B(5,0,0)->S(10,0,0), 17..22s: one fifth at18 gives X6.
    assert pose["world_pos"] == [6, 0, 0]
    assert pose["carrying_hu_ids"] == ["HU1"]
    assert pose["planned_end_tick"] == 22_000_000
    assert pose["observed_tick"] == 18_000_000
    assert hu_location_at(run, "HU1", 18_000_000) == {
        "kind": "worker_attachment",
        "actor_id": "R01",
        "hu_id": "HU1",
    }
    with pytest.raises(ValueError, match="observed"):
        actor_pose_at(run, "R01", 19_000_000)


def test_return_is_empty_and_stock_pose_never_uses_service_node() -> None:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(25_000_000, 40_000_000)
    run = build_manual_run(
        profile, graph, outcome, graph_document=document, end_tick_limit=40_000_000
    )
    assert actor_pose_at(run, "R01", 25_000_000)["carrying_hu_ids"] == []
    assert hu_location_at(run, "HU1", 25_000_000) == {
        "kind": "storage_slot",
        "slot_id": "SLOT",
        "hu_id": "HU1",
    }
