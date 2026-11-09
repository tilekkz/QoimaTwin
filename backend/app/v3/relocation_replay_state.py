"""Build arbitrary settled N1 cuts from journal state, without future snapshot substitution."""

from dataclasses import fields
from typing import cast

from app.v3.api_coordinator_replay_projection import project_snapshot as project_base
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_native_decode import encode
from app.v3.coordinator_run_definitions import Definitions
from app.v3.coordinator_run_projection import _compact
from app.v3.coordinator_run_validation import Journal
from app.v3.coordinator_seek_state import snapshot as base_snapshot
from app.v3.flow_profile_sources import _same_types
from app.v3.interface import Json
from app.v3.relocation_native_decode import decode
from app.v3.relocation_native_projection import _expand
from app.v3.relocation_observe import RelocationSnapshot
from app.v3.relocation_run_validation import RelocationJournal


def snapshot(journal: Journal, tick: int, last_seq: int) -> CoordinatorSnapshot:
    base = base_snapshot(journal, tick, last_seq)
    if not isinstance(journal, RelocationJournal):
        return base
    values = {field.name: getattr(base, field.name) for field in fields(CoordinatorSnapshot)}
    return RelocationSnapshot(
        **values,
        relocations=tuple(journal.progress.views.values()),
        derived_sources=tuple(sorted(journal.progress.derived.items())),
    )


def reduce(journal: Journal, outcome: CoordinatorOutcome, tick: int) -> CoordinatorSnapshot:
    captures = {
        s.tick: s
        for s in (*outcome.checkpoints, outcome.at_horizon, outcome.at_end)
        if s.tick <= tick
    }
    cursor, events = 0, outcome.events
    boundaries = {0, tick, *captures, *(e.tick for e in events if e.tick <= tick)}
    for boundary in sorted(boundaries):
        while cursor < len(events) and events[cursor].tick <= boundary:
            journal.apply(events[cursor])
            cursor += 1
        journal.settle(boundary)
        if boundary in captures:
            journal.check(captures[boundary])
    result = snapshot(journal, tick, cursor - 1)
    journal.check(result)
    if tick in captures and encode(result) != encode(captures[tick]):
        raise ValueError("Relocation replay differs from its verified settled capture")
    return result


def project_snapshot(profile: CoordinatorProfile, point: CoordinatorSnapshot) -> Json:
    if type(point) is CoordinatorSnapshot:
        return project_base(profile, point)
    if type(point) is not RelocationSnapshot:
        raise ValueError("Exact relocation replay snapshot required")
    decoded = decode(RelocationSnapshot, encode(point))
    if not _same_types(point, decoded):
        raise ValueError("Relocation replay state has a substituted native type")
    compact = _compact(decoded)
    expanded = _expand(RelocationSnapshot, compact, Definitions(profile))
    restored = decode(RelocationSnapshot, expanded)
    if encode(restored) != encode(point):
        raise ValueError("Relocation replay definitions differ from exact input authority")
    return cast(Json, compact)
