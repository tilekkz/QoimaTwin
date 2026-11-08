"""C09 manual mode projection distinguishes absent metadata from explicit cargo denials."""

from copy import deepcopy
from typing import Any

import pytest

from app.v3.receipt_profile_permissions import project_manual_cargo


def test_source_walk_absence_projects_only_pedestrian_small_permission() -> None:
    pedestrian = {"arc_id": "p", "allowed_modes": ["pedestrian"], "length_m": 3}
    forklift = {"arc_id": "f", "allowed_modes": ["forklift"], "length_m": 4}
    links: dict[str, Any] = {"walk_graph": {"arcs": [pedestrian, forklift]}}
    before = deepcopy(forklift)
    project_manual_cargo(links)
    assert pedestrian["allowed_cargo_archetype_ids"] == ["SMALL_CARTON"]
    assert pedestrian["length_m"] == 3 and pedestrian["allowed_modes"] == ["pedestrian"]
    assert forklift == before


@pytest.mark.parametrize(
    "restriction",
    [
        {"cargo_transport_supported": False},
        {"allowed_cargo_archetype_ids": []},
        {"allowed_cargo_archetype_ids": ["STANDARD_CARTON"]},
        {"cargo_transport_supported": True},
    ],
)
def test_explicit_cargo_statement_is_not_replaced_by_absence_policy(
    restriction: dict[str, Any],
) -> None:
    arc = {"arc_id": "p", "allowed_modes": ["pedestrian"], **restriction}
    before = deepcopy(arc)
    project_manual_cargo({"walk_graph": {"arcs": [arc]}})
    assert arc == before
