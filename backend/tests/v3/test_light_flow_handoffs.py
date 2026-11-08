"""Controlled package replacement, exact service-window finish and opt-in settled observation."""

from dataclasses import replace

from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowSnapshot
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def test_larger_parcel_is_loaded_at_current_station_pose_without_rewriting_prefix() -> None:
    profile = hand_profile()
    carrier, parcel = profile.materials
    small, large = parcel.recipe, carrier.recipe
    carrier = replace(carrier, recipe=replace(carrier.recipe, outer=small.outer, inner=small.inner))
    parcel = replace(parcel, recipe=replace(parcel.recipe, outer=large.outer, inner=large.inner))
    result = LightFlowEngine(replace(profile, materials=(carrier, parcel)), source_catalog()).run(
        195_000_000, 220_000_000
    )
    assert result.status == "complete" and result.at_end.tick == 197_170_000
    change = next(e for e in result.events if e.kind == "belt:container_replaced")
    assert change.tick == 49_915_448 and change.belt_event is not None
    prefix = [e.belt_event for e in result.events if e.belt_event and e.seq < change.seq]
    assert {e.payload_id for e in prefix} == {"C1"}
    assert change.belt_event.payload_id == "P1"
    assert prefix[-1].pose == change.belt_event.pose
    assert result.at_end.belt.leases == ()


def test_admitted_drain_can_finish_port_service_exactly_at_window_end_after_horizon() -> None:
    profile = hand_profile()
    profile = replace(profile, port=replace(profile.port, windows=((180_000_000, 200_000_000),)))
    result = LightFlowEngine(profile, source_catalog()).run(195_000_000, 220_000_000)
    assert result.at_horizon.balance.shipped_units_by_sku == ()
    assert result.status == "complete" and result.at_end.tick == 205_000_000
    assert next(e.tick for e in result.events if e.kind == "shipped") == 200_000_000
    worker = next(w for w in result.at_end.workers if w.actor_id == "S01")
    assert worker.queue_ticks == 7_830_000  # reached service172.17; window opens180


def test_callback_reports_current_settled_state_and_cannot_rewrite_earlier_stock() -> None:
    observations: list[tuple[FlowSnapshot, int]] = []
    engine = LightFlowEngine(
        hand_profile(),
        source_catalog(),
        on_tick_settled=lambda value, seq: observations.append((value, seq)),
    )
    outcome = engine.run(8_000_000, 8_000_000)
    initial = next(s for s, _ in observations if s.tick == 0)
    picked = next(s for s, _ in observations if s.tick == 6_000_000)
    assert all(p.container_id == "HU1" for p in initial.stock.locations)
    assert sum(p.container_id == "C1" for p in picked.stock.locations) == 3
    assert all(seq == s.last_seq for s, seq in observations)
    assert picked.cart.operation is not None and picked.cart.operation.target_node == "PARK"
    assert outcome.at_end.cart.node is None  # actual cart motion6..9 has not completed
