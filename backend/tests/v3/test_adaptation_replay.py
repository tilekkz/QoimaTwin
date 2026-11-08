"""Sequential, disposable planning projection of C11 transfers and exact route recomputation.

Source facts used as oracles: the baseline assignment slot occupancy and layout-links arcs,
read directly from the pinned JSON (not through the adapter).
"""

import copy
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.v3.adaptation_compare import plan_horizon
from app.v3.adaptation_source import AdaptationPackage, load_adaptation_package

BACKEND = Path(__file__).parents[2]
SOURCE = BACKEND / "data/v3-proposal/docs/v3/contract-proposals"


@pytest.fixture(scope="module")
def package() -> AdaptationPackage:
    return load_adaptation_package(
        BACKEND / "data/v3-adaptation-proposal", BACKEND / "data/v3-proposal"
    )


def _occupied() -> set[str]:
    rows = json.loads((SOURCE / "baseline-assignment-v3.json").read_bytes())["assignments"]
    return {row["slot_id"] for row in rows}


def test_dependent_destinations_are_initially_occupied_but_replay_in_sequence(
    package: AdaptationPackage,
) -> None:
    occupied = _occupied()
    for periods, dependent in ((2, [2]), (4, [2, 4, 7, 8]), (8, [2, 4, 7, 8])):
        transfers = package.horizon_document(periods)["transfers"]
        initially_taken = [t["sequence"] for t in transfers if t["to_slot_id"] in occupied]
        assert initially_taken == dependent
        result = plan_horizon(package, periods)
        assert [t.sequence for t in result.transfers if t.released_by_sequence] == dependent


def _module_of(slot_id: str) -> str:
    slots = json.loads((SOURCE / "storage-slots-v3.json").read_bytes())["slots"]
    return str(next(s["module_id"] for s in slots if s["slot_id"] == slot_id))


def _plan(package: AdaptationPackage, periods: int, document: Any) -> None:
    plan_horizon(package, periods, document=document)


def test_reordered_transfers_are_rejected(package: AdaptationPackage) -> None:
    document = copy.deepcopy(package.horizon_document(2))
    first, second = document["transfers"]
    first["sequence"], second["sequence"] = 2, 1
    document["transfers"] = [second, first]
    with pytest.raises(ValueError, match="occupied"):
        _plan(package, 2, document)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("to_slot_id", "v3:slot:STANDARD_W:001:L3:B1", "reserve|blocked|family|admission"),
        ("to_slot_id", "v3:slot:SMALL_W:017:L1:B1", "family|admission"),
        ("from_slot_id", "v3:slot:STANDARD_W:009:L1:B2", "origin"),
        ("handling_unit_id", "v3:HU:initial:DEMO_001:01", "origin|archetype|sku"),
    ],
)
def test_impossible_transfer_rows_are_rejected(
    package: AdaptationPackage, field: str, value: str, message: str
) -> None:
    document = copy.deepcopy(package.horizon_document(2))
    document["transfers"][0][field] = value
    if field == "to_slot_id":  # keep the module consistent so the slot rule itself is tested
        document["transfers"][0]["to_module_id"] = _module_of(value)
    with pytest.raises(ValueError, match=message):
        _plan(package, 2, document)


def _arc_lengths() -> dict[str, F]:
    links = json.loads((SOURCE / "layout-links-v3.json").read_bytes())
    arcs = [*links["walk_graph"]["arcs"], *links["vehicle_graph"]["arcs"]]
    return {arc["arc_id"]: F(str(arc["length_m"])) for arc in arcs}


def test_route_lengths_come_from_exact_arc_facts(package: AdaptationPackage) -> None:
    lengths = _arc_lengths()
    for transfer in plan_horizon(package, 4).transfers:
        for route in (transfer.loaded_route, transfer.reverse_route):
            assert route.length_m == sum((lengths[a] for a in route.arc_ids), F(0))
        assert not set(transfer.loaded_route.arc_ids) & set(transfer.reverse_route.arc_ids)


@pytest.mark.parametrize("corruption", ["gap", "pedestrian_only", "reused_reverse", "endpoint"])
def test_corrupted_routes_are_rejected(package: AdaptationPackage, corruption: str) -> None:
    document = copy.deepcopy(package.horizon_document(2))
    transfer = document["transfers"][0]  # manual_cart walk route
    if corruption == "gap":
        del transfer["loaded_route"]["arc_ids"][1]
    if corruption == "pedestrian_only":
        transfer["loaded_route"]["arc_ids"][0] = "v3:module:FLEX_E:001:B1:worker:segment:000:f"
    if corruption == "reused_reverse":
        transfer["conservative_reverse_route"] = copy.deepcopy(transfer["loaded_route"])
    if corruption == "endpoint":
        transfer["loaded_route"]["to_node_id"] = "v3:service:OUT_S_EXPRESS"
    with pytest.raises(ValueError):
        _plan(package, 2, document)


def test_projection_never_touches_the_pinned_documents(package: AdaptationPackage) -> None:
    before = copy.deepcopy(package.horizon_document(8))
    plan_horizon(package, 8)
    assert package.horizon_document(8) == before
