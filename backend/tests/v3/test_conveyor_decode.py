"""Untrusted structural inputs must fail before static conveyor use."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.v3.conveyor_source import decode_conveyor_document


def document() -> Any:
    return json.loads(Path("data/v3-conveyor-proposal/conveyor-v3.json").read_bytes())


@pytest.mark.parametrize(
    "path,value",
    [
        (("nodes",), []),
        (("nodes",), {}),
        (("nodes", 0), "not an object"),
        (("nodes", 0, "node_id"), ""),
        (("nodes", 0, "world_pos"), [1, 2]),
        (("nodes", 0, "world_pos"), [True, 2, 3]),
        (("edges", 0, "length_m"), 0),
        (("edges", 0, "length_m"), "NaN"),
        (("source_assumptions", "speed_m_s"), 0),
        (("source_assumptions", "transfer_dwell_s"), 0.5),
        (("cells", 0, "max_handling_units"), True),
        (("cells", 0, "max_handling_units"), 0),
        (("cells", 0, "max_handling_units"), 2),
        (("cells", 0, "resource_id"), "V3_FEED"),
        (("resources", 0, "member_cell_ids"), []),
        (("resources", 0, "member_cell_ids"), ["V3-C-MAIN-000", "V3-C-MAIN-000"]),
        (("resources", 0, "per_cell_capacity"), True),
        (("resources", 1, "capacity"), 2),
        (("packing_stations", 0, "work_node_id"), "absent"),
        (("payload_admission", "allowed"), ["HEAVY_BOX"]),
        (("payload_admission", "maximum_footprint_m"), [1]),
        (("layout_version",), "unknown"),
        (("not_an_actual_engine_run",), False),
        (("units", "length"), "cm"),
    ],
)
def test_malformed_source_fields_reject(path: tuple[str | int, ...], value: Any) -> None:
    raw = document()
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        decode_conveyor_document(raw)


@pytest.mark.parametrize("value", [None, [], "not document", {}])
def test_malformed_document_rejects(value: Any) -> None:
    with pytest.raises(ValueError):
        decode_conveyor_document(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("theta_range", [0]),
        ("theta_range", [0, 1]),
        ("theta_range", [True, -1]),
        ("position", [1, 1, 1]),
    ],
)
def test_arc_cell_does_not_invent_straight_geometry(field: str, value: Any) -> None:
    raw = document()
    arc = next(c for c in raw["cells"] if c["cell_id"] == "V3-C-ARC-00")
    arc[field] = value
    with pytest.raises(ValueError):
        decode_conveyor_document(raw)


def test_arc_direction_is_explicit_not_a_reversible_default() -> None:
    raw = document()
    arc = next(e for e in raw["edges"] if e["edge_id"] == "v3:conv:entry-arc")
    arc["theta_end_rad"] = 1
    with pytest.raises(ValueError):
        decode_conveyor_document(raw)
