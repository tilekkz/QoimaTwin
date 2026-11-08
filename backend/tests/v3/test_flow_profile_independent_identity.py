"""Two explicit same-HU requests distinguish unordered sets from declared sequences."""

import copy
import hashlib
import json
from typing import Any

import pytest

from app.v3.flow_profile import CompiledLightProfile, compile_light_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


def two_orders() -> dict[str, Any]:
    value = document()
    next(a for a in value["actors"] if a["actor_id"] == "P02")["speed_m_s"] = {
        "numerator": 1,
        "denominator": 2,
    }
    for owner in value["owners"]:
        if owner["owner_id"] in {"carrier-pool", "package-pool", "empties", "shipped"}:
            owner["capacity"] = 2
    value["owners"].append({"owner_id": "belt:O2", "kind": "workstation", "capacity": 1})
    extras = [dict(row, container_id=row["container_id"][0] + "2") for row in value["materials"]]
    value["materials"].extend(extras)
    second = copy.deepcopy(value["orders"][0])
    second.update(order_id="O2", carrier_id="C2", package_id="P2", arrival_tick=1_000_000)
    for key in ("carrier_placements", "package_placements"):
        for index, placement in enumerate(second[key], start=4):
            placement["unit_id"] = second["source_hu"] + f":unit:{index:04}"
    value["orders"].append(second)
    return value


@pytest.fixture(name="baseline", scope="module")
def baseline_fixture() -> CompiledLightProfile:
    return compile_light_profile(source_bundle(), source_catalog(), two_orders())


def test_two_order_set_permutations_and_reduced_fractions_have_identical_inputs(
    baseline: CompiledLightProfile,
) -> None:
    value = two_orders()
    for key in ("actors", "owners", "materials", "recipes", "orders"):
        value[key].reverse()
    next(a for a in value["actors"] if a["actor_id"] == "P02")["speed_m_s"] = {
        "numerator": 2,
        "denominator": 4,
    }
    value["orders"][0]["carrier_placements"][0]["position"][0] = {
        "numerator": 0,
        "denominator": 999,
    }
    result = compile_light_profile(source_bundle(), source_catalog(), value)
    assert result.frozen_bytes == baseline.frozen_bytes and result.input_hash == baseline.input_hash
    assert hashlib.sha256(result.frozen_bytes).hexdigest() == result.input_hash
    frozen = json.loads(result.frozen_bytes)
    assert len(frozen["initial_state"]["stock"]["containers"]) == 534  # 530 + explicit4.
    assert len(result.profile.actors) == 24 and len(result.profile.materials) == 4
    assert {a.actor_id for a in result.profile.actors} == {
        *(f"P{i:02}" for i in range(1, 13)),
        *(f"K{i:02}" for i in range(1, 7)),
        "R01",
        "R02",
        "S01",
        "S02",
        "F01",
        "F02",
    }
    assert [o.order_id for o in result.profile.orders] == ["O1", "O2"]
    assert result.profile.orders[0].source_hu == result.profile.orders[1].source_hu


def test_placement_list_order_remains_an_explicit_identity_choice(
    baseline: CompiledLightProfile,
) -> None:
    value = two_orders()
    value["orders"][0]["carrier_placements"].reverse()
    result = compile_light_profile(source_bundle(), source_catalog(), value)
    assert result.input_hash != baseline.input_hash
    assert (
        result.profile.orders[0].carrier_placements
        == (baseline.profile.orders[0].carrier_placements[::-1])
    )


def test_changing_second_arrival_changes_identity_without_allocating_new_stock(
    baseline: CompiledLightProfile,
) -> None:
    value = two_orders()
    value["orders"][1]["arrival_tick"] = 2_000_000
    result = compile_light_profile(source_bundle(), source_catalog(), value)
    assert result.input_hash != baseline.input_hash
    assert len(result.profile.stock.containers) == 530 and len(result.profile.stock.units) == 12256
    assert result.profile.stock == baseline.profile.stock
