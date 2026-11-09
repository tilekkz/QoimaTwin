"""Prewritten N0/N4 hand arithmetic; these are not source-scale acceptance claims."""

from unittest.mock import patch

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_pair_hand import compare_hand_coordinator_profiles
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_noop_executes_two_real_worlds_and_compares_all_observations() -> None:
    target = "app.v3.coordinator_pair_execute.CoordinatorEngine"
    with patch(target, wraps=CoordinatorEngine) as engine:
        result = compare_hand_coordinator_profiles(
            multi_profile(candidate=False),
            multi_profile(candidate=False),
            receipt_conveyor(),
            300 * SECOND,
            400 * SECOND,
            scenario="N0",
        )
    report = result.report
    assert engine.call_count == 2
    assert report["executions"] == 2 and report["verdict"] == "demonstrated"
    assert report["scope"] == "analytical_fixture"
    assert report["evidence"]["events_equal"] is True
    assert report["evidence"]["observations_equal"] is True
    assert report["baseline"]["event_sha256"] == report["candidate"]["event_sha256"]
    assert result.baseline_inputs == result.candidate_inputs
    report["verdict"] = "changed by caller"
    assert result.report["verdict"] == "demonstrated"


def test_two_helpers_do_actual_work_and_return_without_added_resources() -> None:
    result = compare_hand_coordinator_profiles(
        multi_profile(candidate=False),
        multi_profile(candidate=True),
        receipt_conveyor(),
        300 * SECOND,
        400 * SECOND,
        scenario="N4",
    )
    report = result.report
    assert report["verdict"] == "demonstrated" and report["full_v3_acceptance"] is False
    assert report["baseline"]["business_complete_tick"] == 319_254_551
    assert report["candidate"]["business_complete_tick"] == 301_170_000
    assert report["baseline"]["resource_drained_tick"] == 324_254_551
    assert report["candidate"]["resource_drained_tick"] == 306_170_000
    assert report["candidate"]["metrics"] == result.candidate_run["metrics"]
    helpers = report["evidence"]["helpers"]
    assert {h["actor_id"] for h in helpers} == {"P11", "P12"}
    assert {h["station_id"] for h in helpers} == {"PK05", "PK06"}
    assert [h["packing_paid_ticks"] for h in helpers] == [4 * SECOND, 4 * SECOND]
    assert [h["transition_paid_ticks"] for h in helpers] == [8 * SECOND, 12 * SECOND]
    assert [h["restored_tick"] for h in helpers] == [160 * SECOND, 160 * SECOND]
    assert all(h["completed_role_transitions"] for h in helpers)
    assert all(h["completed_orders"] == 1 and h["demonstrated"] for h in helpers)
    assert report["capabilities"]["N1"] is False and report["capabilities"]["N3"] is False


def test_cap_during_paid_return_does_not_report_future_restoration() -> None:
    result = compare_hand_coordinator_profiles(
        multi_profile(candidate=False),
        multi_profile(candidate=True),
        receipt_conveyor(),
        158 * SECOND,
        158 * SECOND,
        scenario="N4",
    )
    report = result.report
    assert report["verdict"] == "not_demonstrated"
    assert report["candidate"]["status"] == "partial"
    helpers = report["evidence"]["helpers"]
    assert [h["transition_paid_ticks"] for h in helpers] == [6 * SECOND, 10 * SECOND]
    assert all(h["restored_tick"] is None and not h["demonstrated"] for h in helpers)
    assert all(h["planned_restore_by_tick"] == 160 * SECOND for h in helpers)
