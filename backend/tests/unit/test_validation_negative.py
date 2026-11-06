"""Each semantic rule rejects a deliberately broken copy of the repository contracts."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.contracts.actors import ActorRegistry
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle
from app.contracts.validation import axis_distance, validate_bundle

Raw = dict[str, Any]
Mutation = Callable[[Raw, Raw, Raw], None]


def _load(contracts_dir: Path, name: str) -> Raw:
    data: Raw = json.loads((contracts_dir / name).read_text(encoding="utf-8"))
    return data


def _issues(contracts_dir: Path, mutate: Mutation) -> list[str]:
    layout = copy.deepcopy(_load(contracts_dir, "layout.example.json"))
    config = copy.deepcopy(_load(contracts_dir, "simulation_defaults.json"))
    actors = copy.deepcopy(_load(contracts_dir, "actors.example.json"))
    mutate(layout, config, actors)
    bundle = ContractBundle(
        directory=contracts_dir,
        layout=Layout.from_data(layout),
        config=SimulationConfig.from_data(config),
        actors=ActorRegistry.from_data(actors),
    )
    return validate_bundle(bundle)


def _set_edge_node(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["picker_graph"]["edges"][0]["b"] = "NOPE"


def _diagonal_edge(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["picker_graph"]["edges"].append({"a": "I01", "b": "N_A02_Z16", "length_m": 1.0})


def _duplicate_node(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["picker_graph"]["nodes"].append(dict(layout["picker_graph"]["nodes"][0]))


def _duplicate_edge(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["picker_graph"]["edges"].append(dict(layout["picker_graph"]["edges"][0]))


def _self_loop(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["picker_graph"]["edges"].append({"a": "I01", "b": "I01", "length_m": 1.0})


def _unknown_rack(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["slots"][0]["rack_id"] = "R_NOPE"


def _pickface_without_node(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["slots"][0]["service_node_id"] = "NOPE"


def _segment_cells(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["segments"][0]["cell_count"] = 53


def _total_cells(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["total_cell_count"] = 180


def _port_off_segment(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["connections"][4]["at"] = [10.0, 0.9, 30]


def _port_half_cell(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["connections"][7]["at"] = [20.5, 0.9, 8]


def _unknown_segment(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["connections"][0]["to_segment_id"] = "NOPE"


def _bad_terminal(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["terminal"]["segment_id"] = "NOPE"


def _station_segment(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["pack_stations"][0]["input_segment_id"] = "NOPE"


def _induction_feed(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["inductions"][0]["feed_segment_id"] = "NOPE"


def _induction_home(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["inductions"][0]["home_node_id"] = "NOPE"


def _count_mismatch(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["counts"]["racks"] = 287


def _relocation_node(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["relocation_buffer_node_id"] = "NOPE"


def _config_version(_l: Raw, config: Raw, _a: Raw) -> None:
    config["layout_version"] = "other"


def _tote_pool(_l: Raw, config: Raw, _a: Raw) -> None:
    config["totes_total"] = 112


def _staffing(_l: Raw, config: Raw, _a: Raw) -> None:
    config["staffing"]["picker"] = 13


def _duplicate_actor(_l: Raw, _c: Raw, actors: Raw) -> None:
    actors["actors"][1]["actor_id"] = actors["actors"][0]["actor_id"]


def _picker_home(_l: Raw, _c: Raw, actors: Raw) -> None:
    actors["actors"][0]["home_node_id"] = "N_A01_Z14"


def _packer_station(_l: Raw, _c: Raw, actors: Raw) -> None:
    actors["actors"][12]["pack_id"] = "PK99"


def _driver_vehicle(_l: Raw, _c: Raw, actors: Raw) -> None:
    actors["actors"][22]["vehicle_id"] = "FL99"


def _driver_home(_l: Raw, _c: Raw, actors: Raw) -> None:
    actors["actors"][22]["home_node_id"] = "FO_HOME"


CASES: list[tuple[str, Mutation, str]] = [
    ("edge to unknown node", _set_edge_node, "unknown node"),
    ("diagonal edge", _diagonal_edge, "not axis-aligned"),
    ("duplicate node", _duplicate_node, "duplicate node"),
    ("duplicate edge", _duplicate_edge, "duplicate edge"),
    ("self loop", _self_loop, "self-loop"),
    ("unknown rack", _unknown_rack, "unknown rack"),
    ("pickface node", _pickface_without_node, "pickface slot"),
    ("segment cells", _segment_cells, "segment LOOP_E"),
    ("total cells", _total_cells, "cells, declared"),
    ("port off segment", _port_off_segment, "off-segment"),
    ("port half cell", _port_half_cell, "off-segment"),
    ("unknown segment", _unknown_segment, "unknown segment"),
    ("terminal", _bad_terminal, "terminal segment"),
    ("station segment", _station_segment, "pack station"),
    ("induction feed", _induction_feed, "feed segment"),
    ("induction home", _induction_home, "home node"),
    ("counts", _count_mismatch, "count racks"),
    ("relocation", _relocation_node, "relocation node"),
    ("config version", _config_version, "config layout_version"),
    ("tote pool", _tote_pool, "tote pool"),
    ("staffing", _staffing, "staffing picker"),
    ("duplicate actor", _duplicate_actor, "duplicate actor"),
    ("picker home", _picker_home, "home is not an induction"),
    ("packer station", _packer_station, "pack station is unknown"),
    ("driver vehicle", _driver_vehicle, "not linked"),
    ("driver home", _driver_home, "inbound graph"),
]


@pytest.mark.parametrize(("case", "mutate", "expected"), CASES, ids=[c[0] for c in CASES])
def test_rule_rejects_broken_contract(
    contracts_dir: Path, case: str, mutate: Mutation, expected: str
) -> None:
    issues = _issues(contracts_dir, mutate)
    assert any(expected in issue for issue in issues), (case, issues)


def test_axis_distance_rejects_vertical_offset() -> None:
    assert axis_distance((0, 0, 0), (0, 1, 0)) is None
    assert axis_distance((0, 0, 0), (3, 0, 0)) == 3
