"""Labor accounting for slotting comparison (01 §10): hand-built action journals."""

from __future__ import annotations

from app.comparison import labor_breakdown
from app.simulation.recorder import Action, ActorState, Waypoint

TPS = 10


def _action(actor: str, state: ActorState, start: int, end: int) -> Action:
    if state is ActorState.TRAVEL:
        points = (Waypoint("a", (0, 0, 0), start), Waypoint("b", (1, 0, 0), end))
        return Action("A", actor, state, "walk", start, end, None, None, points)
    return Action("A", actor, state, "op", start, end, None, (0, 0, 0))


def test_labor_is_travel_plus_service_with_blocked_and_wait_separate() -> None:
    actions = [
        _action("P1", ActorState.TRAVEL, 0, 30),  # 3 s
        _action("P1", ActorState.BUSY_SERVICE, 30, 50),  # 2 s
        _action("P1", ActorState.BLOCKED, 50, 70),  # 2 s
        _action("K1", ActorState.WAIT_RESOURCE, 0, 40),  # 4 s
        _action("K1", ActorState.BUSY_SERVICE, 40, 140),  # 10 s, clipped to 6 s at 100
    ]
    roles = {"P1": "picker", "P2": "picker", "K1": "packer"}
    result = labor_breakdown(actions, roles, open_blocks=[("P2", 80)], cutoff_tick=100, tps=TPS)
    assert result.by_actor["P1"].labor_s == 5
    assert result.by_actor["P1"].blocked_s == 2
    assert result.by_actor["P2"].blocked_s == 2  # open block from 80 clipped at 100
    assert result.by_actor["P2"].labor_s == 0
    assert result.by_actor["K1"].busy_service_s == 6
    assert result.by_actor["K1"].wait_resource_s == 4
    assert result.by_role["picker"].labor_s == 5
    assert result.by_role["picker"].blocked_s == 4
    assert result.by_role["packer"].labor_s == 6
    assert result.total_labor_s == 11
    assert result.labor_ticks == 110


def test_actions_entirely_after_cutoff_count_zero() -> None:
    actions = [_action("P1", ActorState.TRAVEL, 120, 150)]
    result = labor_breakdown(actions, {"P1": "picker"}, open_blocks=[], cutoff_tick=100, tps=TPS)
    assert result.by_actor["P1"].labor_s == 0
    assert result.total_labor_s == 0
