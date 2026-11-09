"""Strict arbitrary settled-state seek; event reduction never starts or restores an engine."""

from typing import Any

from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorSnapshot
from app.v3.coordinator_run import _validate_native
from app.v3.coordinator_run_inventory import same
from app.v3.coordinator_run_validation import Journal
from app.v3.coordinator_seek_state import snapshot
from app.v3.flow_profile_sources import _pinned_reference
from app.v3.native_read_context import _NativeReadContext


def replay_coordinator(run: dict[str, Any], *, inputs: bytes, tick: int) -> CoordinatorSnapshot:
    if type(tick) is not int or tick < 0:
        raise ValueError("Coordinator seek requires an exact nonnegative integer tick")
    return _replay_context(_validate_native(run, inputs=inputs), tick)


def _replay_context(context: _NativeReadContext, tick: int) -> CoordinatorSnapshot:
    if type(tick) is not int or tick < 0:
        raise ValueError("Coordinator seek requires an exact nonnegative integer tick")
    if tick > context.outcome.at_end.tick:
        raise ValueError("Coordinator seek cannot infer unobserved future state")
    frozen, outcome = context.inputs, context.outcome
    _, source, _ = _pinned_reference()
    journal = Journal(frozen.profile, source, outcome, frozen.horizon_tick)
    return _reduce(journal, outcome, tick)


def _reduce(journal: Journal, outcome: CoordinatorOutcome, tick: int) -> CoordinatorSnapshot:
    captures = {
        s.tick: s
        for s in (*outcome.checkpoints, outcome.at_horizon, outcome.at_end)
        if s.tick <= tick
    }
    cursor, events = 0, outcome.events
    for boundary in sorted({*captures, tick}):
        while cursor < len(events) and events[cursor].tick <= boundary:
            journal.apply(events[cursor])
            cursor += 1
        if boundary in captures:
            journal.check(captures[boundary])
    result = snapshot(journal, tick, cursor - 1)
    journal.check(result)
    if tick in captures:
        same(result, captures[tick], "Coordinator seek differs from original settled capture")
    return result
