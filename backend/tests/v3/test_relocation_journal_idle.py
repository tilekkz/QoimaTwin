"""A partial relocation cannot fabricate idle time between its ungated paid steps."""

from dataclasses import replace
from hashlib import sha256

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.relocation_native_projection import project_outcome
from app.v3.relocation_observe import RelocationOutcome, RelocationSnapshot
from tests.v3.test_relocation_run_validation import recorded, validate
from tests.v3.test_relocation_runtime_fixtures import SECOND


def idle_history(result: RelocationOutcome, gap: int) -> RelocationOutcome:
    lost = [
        e
        for e in result.events
        if e.order_id == "N1" and e.kind == "operation_started" and e.tick == gap
    ]
    assert len(lost) == 1 and lost[0].operation is not None
    operation = lost[0].operation
    rows = tuple(
        replace(e, seq=i) for i, e in enumerate(e for e in result.events if e is not lost[0])
    )

    def capture(state: RelocationSnapshot) -> RelocationSnapshot:
        if state.tick >= gap:
            state = replace(
                state,
                workers=tuple(
                    replace(
                        w,
                        operation=None,
                        node=operation.source_node,
                        waiting_since=gap,
                        paid_ticks=gap,
                        queue_ticks=state.tick - gap,
                    )
                    if w.actor_id == "S01"
                    else w
                    for w in state.workers
                ),
            )
        return replace(state, last_seq=sum(e.tick <= state.tick for e in rows) - 1)

    return replace(
        result,
        events=rows,
        at_horizon=capture(result.at_horizon),
        at_end=capture(result.at_end),
        checkpoints=tuple(capture(s) for s in result.checkpoints),
    )


@pytest.mark.parametrize(
    ("gap", "cap", "owner"),
    [
        (0, SECOND, "slot"),
        (4 * SECOND, 5 * SECOND, "actor:S01"),
        (8 * SECOND, 9 * SECOND, "target"),
    ],
)
def test_admitted_relocation_cannot_invent_a_queue_gap(gap: int, cap: int, owner: str) -> None:
    profile, result = recorded(cap)
    validate(profile, result, cap, cap)
    altered = idle_history(result, gap)
    original = canonical_bytes(project_outcome(profile.coordinator, result))
    forged = canonical_bytes(project_outcome(profile.coordinator, altered))
    assert sha256(original).digest() != sha256(forged).digest()
    assert (
        next(c.owner_id for c in altered.at_end.stock.containers if c.container_id == "HU1")
        == owner
    )
    assert len(altered.at_end.leases) == 3
    with pytest.raises(ValueError, match=r"Relocation.*operation"):
        validate(profile, altered, cap, cap)
