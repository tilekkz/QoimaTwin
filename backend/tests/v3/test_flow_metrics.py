"""Hand-derived inclusive business counts and half-open exposure metrics."""

from dataclasses import replace

import pytest

from app.v3.flow_metrics import summary
from tests.v3.test_flow_metrics_fixtures import metric_outcome, metric_profile, observation
from tests.v3.test_light_flow_fixtures import SECOND


def test_horizon_backlog_and_linear_cycle_statistics_use_observed_handoffs() -> None:
    profile = metric_profile()
    result = summary(profile, metric_outcome(profile))
    horizon, end = result["at_horizon"], result["at_end"]
    assert result["counts_boundary"] == "settled_tick_inclusive"
    assert result["integral_window"] == "[0,T)"
    assert horizon["arrived_orders"] == 2
    assert horizon["completed_orders"] == 1
    assert horizon["backlog_orders"] == result["backlog_at_horizon"] == 1
    assert horizon["completed_units"] == 3
    assert horizon["mean_cycle_s"] == horizon["p95_cycle_s"] == 8
    assert end["completed_orders"] == 2
    assert end["backlog_orders"] == 0
    assert end["completed_units"] == 6
    assert end["mean_cycle_s"] == 11
    assert end["p95_cycle_s"] == pytest.approx(13.7)


def test_paid_exposure_keeps_all_24_roster_members_and_role_denominators() -> None:
    profile = metric_profile()
    window = summary(profile, metric_outcome(profile))["at_horizon"]
    assert window["worker_paid_s"] == 6
    assert len(window["worker_paid_s_by_actor"]) == 24
    assert window["worker_paid_s_by_actor"]["P12"] == 0
    assert window["worker_utilization_by_actor"]["P01"] == 0.3
    assert window["roster_utilization"] == 0.025  # 6 / (24 * 10)
    assert window["role_pool_size"] == {
        "pick": 12,
        "pack": 6,
        "receive": 2,
        "ship": 2,
        "forklift": 2,
    }
    assert window["role_pool_utilization"]["pick"] == 0.025  # 3 / (12 * 10)
    assert window["role_pool_utilization"]["pack"] == pytest.approx(1 / 30)
    assert window["role_pool_utilization"]["ship"] == 0.05
    assert window["role_pool_utilization"]["forklift"] == 0


def test_time_weighted_waits_are_distinct_from_work_in_progress_and_paid_work() -> None:
    profile = metric_profile()
    queues = summary(profile, metric_outcome(profile))["at_horizon"]["queues"]
    assert queues["unadmitted_order_seconds"] == 3  # (1 - 0) + (6 - 4)
    assert queues["mean_unadmitted_orders"] == 0.3
    assert queues["unfinished_order_seconds"] == 14  # (8 - 0) + (10 - 4)
    assert queues["mean_unfinished_orders"] == 1.4
    assert queues["assigned_worker_wait_person_seconds"] == 3
    assert queues["mean_waiting_workers"] == 0.3
    assert queues["stopped_belt_carrier_seconds"] == 5
    assert queues["mean_stopped_belt_carriers"] == 0.5


def test_completion_at_boundary_counts_but_paid_return_is_not_cycle_end() -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    result = summary(profile, replace(outcome, at_horizon=observation(profile, 8)))
    assert result["at_horizon"]["completed_orders"] == 1
    assert result["at_horizon"]["mean_cycle_s"] == 8
    assert result["at_end"]["mean_cycle_s"] == 11


def test_zero_window_has_no_defined_utilization_or_completed_cycle() -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    window = summary(profile, replace(outcome, at_horizon=observation(profile, 0)))["at_horizon"]
    assert window["arrived_orders"] == window["backlog_orders"] == 1
    assert window["completed_orders"] == 0
    assert window["mean_cycle_s"] is None and window["p95_cycle_s"] is None
    assert window["roster_utilization"] is None
    assert all(value is None for value in window["role_pool_utilization"].values())
    assert window["queues"]["mean_unadmitted_orders"] is None


def test_partial_open_order_accumulates_wait_only_to_observed_cap() -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    state = outcome.at_horizon
    second = replace(state.orders[1], admitted_tick=None)
    partial = replace(state, orders=(state.orders[0], second))
    result = summary(profile, replace(outcome, status="partial", at_end=partial))
    assert result["at_end"]["backlog_orders"] == 1
    assert result["at_end"]["queues"]["unadmitted_order_seconds"] == 7  # 1 + (10 - 4)


def test_idle_time_after_early_finish_changes_denominator_without_new_labor() -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    result = summary(profile, replace(outcome, at_horizon=observation(profile, 30)))
    assert result["at_horizon"]["worker_paid_s"] == result["at_end"]["worker_paid_s"] == 12
    assert result["at_horizon"]["roster_utilization"] == pytest.approx(12 / 720)
    assert result["at_end"]["roster_utilization"] == 0.025


def test_input_order_permutation_does_not_change_metrics() -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    shuffled = replace(
        profile, orders=tuple(reversed(profile.orders)), actors=tuple(reversed(profile.actors))
    )
    state = outcome.at_horizon
    permuted = replace(
        state, workers=tuple(reversed(state.workers)), orders=tuple(reversed(state.orders))
    )
    assert summary(shuffled, replace(outcome, at_horizon=permuted)) == summary(profile, outcome)


@pytest.mark.parametrize(
    "paid,waited", [(-1, 0), (True, 0), (11 * SECOND, 0), (7 * SECOND, 4 * SECOND)]
)
def test_invalid_worker_exposure_rejects(paid: int, waited: int) -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    state = outcome.at_horizon
    worker = replace(state.workers[0], paid_ticks=paid, queue_ticks=waited)
    with pytest.raises(ValueError, match="exposure"):
        summary(
            profile,
            replace(outcome, at_horizon=replace(state, workers=(worker, *state.workers[1:]))),
        )


def test_missing_or_future_business_observation_rejects() -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    with pytest.raises(ValueError, match="identit"):
        summary(profile, replace(outcome, at_end=replace(outcome.at_end, orders=())))
    future = replace(outcome.at_horizon.orders[0], shipped_tick=11 * SECOND)
    state = replace(outcome.at_horizon, orders=(future, outcome.at_horizon.orders[1]))
    with pytest.raises(ValueError, match="observed"):
        summary(profile, replace(outcome, at_horizon=state))


@pytest.mark.parametrize("belt_tick,exposure", [(0, 1), (False, 0)])
def test_empty_belt_window_cannot_have_exposure_or_a_boolean_clock(
    belt_tick: int,
    exposure: int,
) -> None:
    profile = metric_profile()
    outcome = metric_outcome(profile)
    zero = observation(profile, 0)
    invalid = replace(zero, belt=replace(zero.belt, tick=belt_tick, queue_ticks=exposure))
    with pytest.raises(ValueError, match="exposure"):
        summary(profile, replace(outcome, at_horizon=invalid))


def test_native_flow_metrics_match_precomputed_business_and_paid_return_oracles() -> None:
    from app.v3.light_flow_engine import LightFlowEngine
    from tests.v3.test_belt_runtime import source_catalog
    from tests.v3.test_light_flow_fixtures import hand_profile

    profile = hand_profile()
    outcome = LightFlowEngine(profile, source_catalog()).run(50 * SECOND, 300 * SECOND)
    result = summary(profile, outcome)
    horizon, end = result["at_horizon"], result["at_end"]
    assert result["backlog_at_horizon"] == 1 and horizon["completed_orders"] == 0
    assert horizon["mean_cycle_s"] is None
    assert horizon["worker_paid_s_by_actor"]["P01"] == 20
    # Approach2 + pack3 + clear1 + paid return already elapsed50-49.915448.
    assert horizon["worker_paid_s_by_actor"]["K06"] == pytest.approx(6.084552)
    assert horizon["worker_paid_s_by_actor"]["S01"] == 0
    assert end["backlog_orders"] == 0 and end["completed_units"] == 3
    assert end["mean_cycle_s"] == end["p95_cycle_s"] == 192.17
    assert end["time_s"] == 197.17  # Five-second paid return after handoff.
    assert end["worker_paid_s"] == 59  # Picker20 + packer8 + shipper31.
    assert end["queues"]["stopped_belt_carrier_seconds"] == 5
