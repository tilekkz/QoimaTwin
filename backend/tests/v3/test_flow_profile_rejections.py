"""Malformed public choices must fail before any runtime or publication."""

from typing import Any

import pytest

from app.v3.flow_profile import compile_light_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


@pytest.mark.parametrize(
    "value",
    [
        True,
        1,
        1.0,
        "1/2",
        {},
        {"numerator": 1},
        {"numerator": True, "denominator": 2},
        {"numerator": 1, "denominator": False},
        {"numerator": 1, "denominator": 0},
        {"numerator": 1, "denominator": -2},
        {"numerator": 1.0, "denominator": 2},
        {"numerator": 1, "denominator": 2, "extra": 0},
    ],
)
def test_malformed_fraction_is_rejected(value: Any) -> None:
    row = document()
    row["actors"][0]["speed_m_s"] = value
    with pytest.raises(ValueError):
        compile_light_profile(source_bundle(), source_catalog(), row)


@pytest.mark.parametrize(
    "case",
    [
        "end_before_h",
        "bool_h",
        "float_h",
        "missing_actor",
        "duplicate_actor",
        "missing_material",
        "duplicate_material",
        "duplicate_recipe",
        "missing_recipe",
        "missing_owner",
        "duplicate_owner",
        "unknown_hu",
        "unknown_unit",
        "overlap",
        "outside",
        "negative_time",
        "derived_actor",
        "derived_order",
    ],
)
def test_invalid_choices_are_rejected(case: str) -> None:
    row = document()
    alter(row, case)
    with pytest.raises(ValueError):
        compile_light_profile(source_bundle(), source_catalog(), row)


def alter(row: dict[str, Any], case: str) -> None:
    if case == "end_before_h":
        row["end_tick"] = row["horizon_tick"] - 1
    elif case == "bool_h":
        row["horizon_tick"] = True
    elif case == "float_h":
        row["horizon_tick"] = 1.0
    elif case == "missing_actor":
        row["actors"].pop()
    elif case == "duplicate_actor":
        row["actors"][-1] = row["actors"][0]
    elif case == "missing_material":
        row["materials"].pop()
    elif case == "duplicate_material":
        row["materials"].append(row["materials"][0])
    elif case == "duplicate_recipe":
        row["recipes"].append(row["recipes"][0])
    elif case == "missing_recipe":
        row["recipes"].pop()
    elif case == "missing_owner":
        row["owners"].pop()
    elif case == "duplicate_owner":
        row["owners"].append(row["owners"][0])
    elif case == "unknown_hu":
        row["orders"][0]["source_hu"] = "missing"
    elif case == "unknown_unit":
        row["orders"][0]["carrier_placements"][0]["unit_id"] = "missing"
    elif case == "overlap":
        row["orders"][0]["carrier_placements"][1]["position"] = row["orders"][0][
            "carrier_placements"
        ][0]["position"]
    elif case == "outside":
        row["orders"][0]["package_placements"][0]["position"][0] = {
            "numerator": 99,
            "denominator": 1,
        }
    elif case == "negative_time":
        row["times"]["pack"] = -1
    elif case == "derived_actor":
        row["actors"][0]["role_capacity"] = 99
    elif case == "derived_order":
        row["orders"][0]["source_node"] = "override"
