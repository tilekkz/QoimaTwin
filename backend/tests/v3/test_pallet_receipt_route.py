"""Tiny literal route oracles, independent of source routing output."""

from fractions import Fraction as F

import pytest

from app.v3.pallet_receipt_route import _shortest
from app.v3.pallet_receipt_types import PalletReceiptError
from app.v3.vehicle_types import ArcGeometry, VehicleArc


def arc(key: str, start: str, end: str, length: int) -> VehicleArc:
    geometry = ArcGeometry("line", F(0), F(0), (F(0), F(0)), (F(0), F(length)))
    return VehicleArc(
        key,
        start,
        end,
        geometry,
        1,
        F(length),
        F(length),
        frozenset({"INBOUND_FORKLIFT_PAIR"}),
        frozenset({"loaded_max"}),
        frozenset({"PALLET_LOAD"}),
        ("lane",),
        ("mixed",),
        F(3),
        F(3),
        None,
        F(0),
        "stop_before_change",
        key,
    )


def test_candidate_cost_is_exact_root_metres_not_elapsed_service_time() -> None:
    graph = {
        "A": [arc("direct", "A", "C", 6), arc("first", "A", "B", 2)],
        "B": [arc("second", "B", "C", 3)],
    }
    assert _shortest(graph, "A", "C") == ("first", "second")


def test_equal_length_routes_have_stable_arc_id_order() -> None:
    graph = {"A": [arc("z", "A", "B", 2), arc("a", "A", "B", 2)]}
    assert _shortest(graph, "A", "B") == ("a",)


def test_reverse_connectivity_is_never_fabricated() -> None:
    with pytest.raises(PalletReceiptError) as error:
        _shortest({"A": [arc("forward", "A", "B", 2)]}, "B", "A")
    assert error.value.code == "NO_PERMITTED_LOADED_ROUTE"
