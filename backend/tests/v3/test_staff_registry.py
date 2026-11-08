"""Bounded source binding and canonical registry identity, not full A/B run identity."""

from collections.abc import Callable
from copy import deepcopy
from fractions import Fraction
from typing import Any

import pytest

from app.v3.staff_registry import compile_staff_registry, require_same_registry
from tests.v3.test_staff_registry_fixtures import SECOND, registry_document


def test_source_has_exact_roster_shared_pools_and_human_station_anchors() -> None:
    registry = compile_staff_registry(registry_document())
    source = registry.source
    assert len(source.actor_ids) == 24
    assert source.receivers == ("R01", "R02")
    assert source.shippers == ("S01", "S02")
    assert len(source.stations) == 6
    pk05 = next(s for s in source.stations if s.station_id == "PK05")
    assert pk05.service_node_id == "v3:service:PK05"
    assert pk05.worker_position == (Fraction(106), Fraction(0), Fraction("6.1"))
    assert pk05.work_node_id == "v3:conv:PK05:WORK"
    assert pk05.work_position == (Fraction(106), Fraction(".92"), Fraction("5.3"))
    assert not registry.operational_admission


def test_set_array_reorder_preserves_canonical_registry_bytes_and_hash() -> None:
    document = registry_document()
    reordered = deepcopy(document)
    for key in ("workers", "unavailability", "station_bindings"):
        reordered[key].reverse()
    for worker in reordered["workers"]:
        worker["eligible_roles"].reverse()
        worker["permitted_equipment"].reverse()
    first, second = compile_staff_registry(document), compile_staff_registry(reordered)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.registry_common_hash == second.registry_common_hash
    require_same_registry(first, second)


@pytest.mark.parametrize("change", ["window", "skill", "equipment", "station"])
def test_common_registry_drift_is_rejected(change: str) -> None:
    original = registry_document()
    changed = deepcopy(original)
    if change == "window":
        changed["unavailability"][0]["end_tick"] += SECOND
    elif change == "skill":
        changed["workers"][10]["eligible_roles"].remove("pack")
    elif change == "equipment":
        changed["workers"][10]["permitted_equipment"] = []
    else:
        changed["station_bindings"][0]["primary_actor_id"] = "K02"
        changed["station_bindings"][1]["primary_actor_id"] = "K01"
    with pytest.raises(ValueError, match="REGISTRY_COMMON_INPUT_DRIFT"):
        require_same_registry(compile_staff_registry(original), compile_staff_registry(changed))


@pytest.mark.parametrize(
    "field,value",
    [("start_tick", True), ("end_tick", 160.0), ("start_tick", -1), ("end_tick", 100 * SECOND)],
)
def test_noninteger_negative_and_empty_periods_rejected(field: str, value: Any) -> None:
    document = registry_document()
    document["unavailability"][0][field] = value
    with pytest.raises(ValueError):
        compile_staff_registry(document)


def test_overlapping_breaks_rejected_but_adjacent_periods_remain_distinct() -> None:
    document = registry_document()
    extra = dict(document["unavailability"][0], start_tick=159 * SECOND, end_tick=170 * SECOND)
    document["unavailability"].append(extra)
    with pytest.raises(ValueError, match="OVERLAPPING_UNAVAILABILITY"):
        compile_staff_registry(document)
    extra["start_tick"] = 160 * SECOND
    registry = compile_staff_registry(document)
    assert len(registry.unavailability) == 3


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_worker",
        "missing_worker",
        "duplicate_worker",
        "unknown_actor",
        "extra_station",
        "missing_station",
        "duplicate_binding",
        "unknown_station",
        "duplicate_primary",
        "unknown_primary",
        "primary_role",
        "missing_primary_skill",
        "unknown_role",
        "duplicate_skill",
        "unknown_equipment",
        "unknown_window_actor",
        "nested_extra",
        "root_extra",
        "wrong_revision",
        "wrong_version",
        "c12",
    ],
)
def test_invalid_registry_documents_fail_closed(mutation: str) -> None:
    document = registry_document()
    mutate(document, mutation)
    with pytest.raises(ValueError):
        compile_staff_registry(document)


def mutate(document: dict[str, Any], mutation: str) -> None:
    workers, bindings = document["workers"], document["station_bindings"]
    changes: dict[str, Callable[[], object]] = {
        "extra_worker": lambda: workers.append(dict(workers[0], actor_id="P13")),
        "missing_worker": lambda: workers.pop(),
        "duplicate_worker": lambda: workers.append(workers[0]),
        "unknown_actor": lambda: workers[0].update(actor_id="ghost"),
        "extra_station": lambda: bindings.append(dict(bindings[0], station_id="PK07")),
        "missing_station": lambda: bindings.pop(),
        "duplicate_binding": lambda: bindings.append(bindings[0]),
        "unknown_station": lambda: bindings[0].update(station_id="ghost"),
        "duplicate_primary": lambda: bindings[0].update(primary_actor_id="K02"),
        "unknown_primary": lambda: bindings[0].update(primary_actor_id="P01"),
        "primary_role": lambda: workers[0].update(primary_role="pack"),
        "missing_primary_skill": lambda: workers[0].update(eligible_roles=["pack"]),
        "unknown_role": lambda: workers[0].update(eligible_roles=["pick", "driver"]),
        "duplicate_skill": lambda: workers[0].update(eligible_roles=["pick", "pick"]),
        "unknown_equipment": lambda: workers[0].update(permitted_equipment=["magic"]),
        "unknown_window_actor": lambda: document["unavailability"][0].update(actor_id="ghost"),
        "nested_extra": lambda: workers[0].update(hidden_workers=1),
        "root_extra": lambda: document.update(full_run_hash="not proven"),
        "wrong_revision": lambda: document.update(source_revision="c12"),
        "wrong_version": lambda: document.update(schema_version="0.2.0"),
        "c12": lambda: document.update(document_kind="C12"),
    }
    changes[mutation]()
