"""B1 strict references and restoration proposals; no caller identity shortcuts."""

from dataclasses import replace
from typing import Any

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.staff_registry import compile_staff_registry
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_staff_registry_fixtures import registry_document


def test_duplicate_station_cannot_hide_behind_an_id_dictionary() -> None:
    profile = staffing_profile()
    with pytest.raises(ValueError, match="SIX_STATIONS"):
        CoordinatorEngine(
            replace(profile, stations=(*profile.stations, profile.stations[0])), receipt_conveyor()
        )


def test_active_belt_station_and_role_worker_anchor_must_agree() -> None:
    profile = staffing_profile()
    stations = tuple(
        replace(s, node_id="H12") if s.station_id == "PK06" else s for s in profile.stations
    )
    with pytest.raises(ValueError, match="STATION_BINDING_MISMATCH"):
        CoordinatorEngine(replace(profile, stations=stations), receipt_conveyor())


def test_b1_primary_role_restoration_requires_declared_actual_home() -> None:
    profile = staffing_profile()
    changed = replace(profile.intents[0], restore_node="ST05")
    with pytest.raises(ValueError, match="RESTORE_HOME_REQUIRED"):
        CoordinatorEngine(replace(profile, intents=(changed,)), receipt_conveyor())


def test_active_flow_packer_must_match_declared_primary_station_binding() -> None:
    document = registry_document()
    document["station_bindings"][4]["primary_actor_id"] = "K06"
    document["station_bindings"][5]["primary_actor_id"] = "K05"
    profile = replace(staffing_profile(), registry=compile_staff_registry(document))
    with pytest.raises(ValueError, match="STATION_BINDING_MISMATCH"):
        CoordinatorEngine(profile, receipt_conveyor())


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_tick", True),
        ("return_tick", 156.0),
        ("restore_by_tick", False),
        ("request_tick", -1),
        ("return_tick", 100 * SECOND),
    ],
)
def test_strict_role_periods(field: str, value: Any) -> None:
    profile = staffing_profile()
    changed = replace(profile.intents[0], **{field: value})
    with pytest.raises(ValueError):
        CoordinatorEngine(replace(profile, intents=(changed,)), receipt_conveyor())


def test_one_tick_too_late_declared_return_is_denied_without_paid_teleport() -> None:
    profile = staffing_profile()
    changed = replace(profile.intents[0], return_tick=156 * SECOND + 1)
    outcome = CoordinatorEngine(replace(profile, intents=(changed,)), receipt_conveyor()).run(
        200 * SECOND, 200 * SECOND
    )
    role = outcome.at_end.roles[0]
    assert role.status == "rejected" and role.reason == "ROLE_WINDOW_TOO_SHORT"
    assert role.departed_tick is None and role.restored_tick is None
    assert outcome.staffing_status == "violated"
    assert next(w for w in outcome.at_end.workers if w.actor_id == "P11").paid_ticks == 0
