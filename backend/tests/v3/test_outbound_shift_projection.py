"""Independent small arithmetic separates C11 shares from C10 intensities."""

from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.input_models import Port
from app.v3.outbound_shift_projection import project_rows
from app.v3.workload_source import _weights


def rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    original = [
        {
            "sku_id": "A",
            "archetype_id": "SMALL_CARTON",
            "expected_outbound_HU_moves": 10,
            "expected_inbound_HU_moves": 2,
            "inbound_port_mix": {"I": 1},
            "outbound_port_mix": {"R": 0.5, "E": 0.5},
            "handling_unit_ids": ["HU:A"],
            "quantity_units": 24,
            "lot_id": "LOT:A",
        }
    ]
    shifted = [
        {
            **original[0],
            "expected_outbound_HU_moves": 999,
            "expected_inbound_HU_moves": 888,
            "inbound_port_mix": {"FOREIGN": 1},
            "outbound_port_mix": {"R": 0.25, "E": 0.75},
        }
    ]
    return original, shifted


def test_only_mix_changes_even_when_c11_intensity_and_inbound_differ() -> None:
    before, after = rows()
    projected, excluded = project_rows(before, after)
    ports = {
        p: Port(p, "outbound", (0, 0, 0), p, 1, 1, ("SMALL_CARTON",), (), ()) for p in ("R", "E")
    }
    result = _weights(projected, "outbound", ports)
    assert {(w.port_id, w.weight) for w in result} == {("R", F(5, 2)), ("E", F(15, 2))}
    assert sum((w.weight for w in result), F(0)) == 10
    assert projected[0]["inbound_port_mix"] == {"I": 1}
    assert projected[0]["expected_inbound_HU_moves"] == 2
    assert projected[0]["handling_unit_ids"] == ["HU:A"]
    assert excluded == ("A",)
    assert before[0]["outbound_port_mix"] == {"R": 0.5, "E": 0.5}
    assert after[0]["expected_outbound_HU_moves"] == 999


@pytest.mark.parametrize("kind", ["sku", "class", "duplicate", "missing"])
def test_projection_rejects_unbound_source_rows(kind: str) -> None:
    before, after = rows()
    if kind == "sku":
        after[0]["sku_id"] = "FOREIGN"
    elif kind == "class":
        after[0]["archetype_id"] = "PALLET_LOAD"
    elif kind == "duplicate":
        after.append(after[0])
    else:
        after.clear()
    with pytest.raises(ValueError):
        project_rows(before, after)
