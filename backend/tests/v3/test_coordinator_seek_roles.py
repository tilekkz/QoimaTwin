"""Exact role boundaries are prewritten from6m/9m travel at1.5m/s."""

from app.v3.coordinator_seek import replay_coordinator
from tests.v3.test_coordinator_seek_fixtures import fresh_run
from tests.v3.test_receipt_flow_fixtures import SECOND


def test_mid_role_route_preserves_future_end_and_only_observed_paid_time() -> None:
    inputs, run, _ = fresh_run("roles")
    state = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=102 * SECOND)
    helpers = {w.actor_id: w for w in state.workers if w.actor_id in {"P11", "P12"}}
    assert len(state.workers) == 24
    for actor, planned in (("P11", 104), ("P12", 106)):
        worker = helpers[actor]
        assert worker.node is None and worker.operation is not None
        assert worker.operation.planned_end_tick == planned * SECOND
        assert worker.paid_ticks == 2 * SECOND
    assert {r.status for r in state.roles} == {"outward"}


def test_role_state_and_exposure_include_exact_arrival_and_paid_return() -> None:
    inputs, run, _ = fresh_run("roles")
    at104 = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=104 * SECOND)
    assert {r.intent_id: r.status for r in at104.roles} == {"I11": "active", "I12": "outward"}
    at105 = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=105 * SECOND)
    assert sum(w.paid_ticks for w in at105.workers) == 9 * SECOND
    assert dict(at105.exposure.role_ticks)["pack"] == 621 * SECOND
    at158 = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=158 * SECOND)
    assert sum(w.paid_ticks for w in at158.workers) == 16 * SECOND
    assert {r.status for r in at158.roles} == {"returning"}
    at160 = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=160 * SECOND)
    assert sum(w.paid_ticks for w in at160.workers) == 20 * SECOND
    assert {r.status for r in at160.roles} == {"restored"}
    assert at160.role_bindings == ()


def test_backward_and_repeated_seek_does_not_share_mutable_journal_state() -> None:
    inputs, run, _ = fresh_run("roles")
    first = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=160 * SECOND)
    earlier = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=102 * SECOND)
    final = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=160 * SECOND)
    assert first == final and first != earlier
    assert all(r.status == "restored" for r in first.roles)
    assert all(r.status == "outward" for r in earlier.roles)
