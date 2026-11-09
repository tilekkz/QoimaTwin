"""Public capability boundaries and ordered geometry remain explicit."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle
from app.v3.settings import default_inputs
from app.v3.whole_profile_io import compile_whole_profile
from app.v3.whole_profile_io_choices import normalize
from app.v3.whole_profile_schema import validate_document, whole_profile_schema
from tests.v3.test_whole_profile_io_schema import document


def test_checked_in_schema_is_exact_and_old_receipt_schema_is_unchanged() -> None:
    root = Path(__file__).parents[2] / "docs/proposals/adaptive-v3"
    assert (
        json.loads((root / "whole-flow-profile.schema.json").read_bytes()) == whole_profile_schema()
    )
    from app.v3.receipt_profile_schema import receipt_profile_schema

    assert "whole_orders" not in receipt_profile_schema()["properties"]


@pytest.mark.parametrize("future", [False, True])
def test_unit_orders_do_not_grant_standard_or_future_picking(future: bool) -> None:
    value = document()
    path = Path(__file__).parents[2] / "docs/proposals/adaptive-v3/light-flow-profile.example.json"
    order = json.loads(path.read_bytes())["orders"][0]
    hu = "RECEIVED-STANDARD-1" if future else "v3:HU:initial:DEMO_111:01"
    order["source_hu"] = hu
    for key in ("carrier_placements", "package_placements"):
        for index, row in enumerate(order[key], 1):
            row["unit_id"] = f"{hu}:unit:{index:04d}"
    value["orders"] = [order]
    bundle = load_v3_bundle(default_inputs())
    with pytest.raises(ValueError, match=r"original.*SMALL"):
        compile_whole_profile(bundle, load_conveyor_source(bundle), value)


def test_path_sequence_is_not_normalized_as_a_set() -> None:
    a = document()
    b = deepcopy(a)
    b["whole_buffers"][0]["path_xz"].reverse()
    validate_document(b)
    assert normalize(a) != normalize(b)
