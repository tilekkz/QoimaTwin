"""Each semantic rule rejects a deliberately broken copy of the repository contracts."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.actors import ActorRegistry
from app.contracts.base import exact
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle, ContractError, load_contract_bundle
from app.contracts.validation import axis_distance, validate_bundle
from app.conveyor.topology import ConveyorTopology, TopologyError

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
    branch = next(s for s in layout["conveyor"]["segments"] if s["segment_id"] == "BRANCH01")
    branch["from"][0] = branch["to"][0] = 20.5
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
    ("port half cell", _port_half_cell, "valid cell boundary"),
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


def _duplicate_id(collection: str, field: str) -> Mutation:
    def mutate(layout: Raw, _c: Raw, _a: Raw) -> None:
        layout[collection][1][field] = layout[collection][0][field]

    return mutate


def _isolate(node_id: str) -> Mutation:
    def mutate(layout: Raw, _c: Raw, _a: Raw) -> None:
        layout["picker_graph"]["edges"] = [
            e for e in layout["picker_graph"]["edges"] if node_id not in (e["a"], e["b"])
        ]

    return mutate


def _config_value(field: str, value: int | float) -> Mutation:
    def mutate(_l: Raw, config: Raw, _a: Raw) -> None:
        config[field] = value

    return mutate


def _segment_role(segment_id: str, role: str) -> Mutation:
    def mutate(layout: Raw, _c: Raw, _a: Raw) -> None:
        next(s for s in layout["conveyor"]["segments"] if s["segment_id"] == segment_id)["role"] = (
            role
        )

    return mutate


def _wrong_service_node(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["slots"][0]["service_node_id"] = "N_A01_Z18"


def _wrong_rack_geometry(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["racks"][0]["root"][0] += 4.5


def _packer_coverage(_l: Raw, _c: Raw, actors: Raw) -> None:
    packers = [a for a in actors["actors"] if a["role"] == "packer"]
    packers[1]["pack_id"] = packers[0]["pack_id"]


def _missing_packer(_l: Raw, config: Raw, actors: Raw) -> None:
    actors["actors"] = [a for a in actors["actors"] if a.get("pack_id") != "PK01"]
    config["staffing"]["packer"] -= 1


def _remove_connection(segment_id: str) -> Mutation:
    def mutate(layout: Raw, _c: Raw, _a: Raw) -> None:
        layout["conveyor"]["connections"] = [
            c
            for c in layout["conveyor"]["connections"]
            if segment_id not in (c["from_segment_id"], c["to_segment_id"])
        ]

    return mutate


def _unreachable_shipping(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["pack_stations"][0]["output_segment_id"] = "LOOP_E"


def _exitless_cycle(layout: Raw, _c: Raw, _a: Raw) -> None:
    layout["conveyor"]["connections"] = [
        c for c in layout["conveyor"]["connections"] if not c["to_segment_id"].startswith("BRANCH")
    ]


def _port_endpoint(source_start: bool) -> Mutation:
    def mutate(layout: Raw, _c: Raw, _a: Raw) -> None:
        link = layout["conveyor"]["connections"][0]
        segment_id = link["from_segment_id"] if source_start else link["to_segment_id"]
        segment = next(s for s in layout["conveyor"]["segments"] if s["segment_id"] == segment_id)
        segment["from"], segment["to"] = segment["to"], segment["from"]

    return mutate


def _rack_size(axis: int, value: float) -> Mutation:
    def mutate(layout: Raw, _c: Raw, _a: Raw) -> None:
        layout["racks"][0]["size"][axis] = value

    return mutate


CASES += [
    ("duplicate pack_id", _duplicate_id("pack_stations", "pack_id"), "duplicate pack_id"),
    (
        "duplicate induction_id",
        _duplicate_id("inductions", "induction_id"),
        "duplicate induction_id",
    ),
    ("duplicate zone_id", _duplicate_id("zones", "zone_id"), "duplicate zone_id"),
    ("isolated home", _isolate("I01"), "picker home I01 cannot reach"),
    ("isolated service", _isolate("N_A01_Z16"), "cannot reach N_A01_Z16"),
    ("isolated relocation home", _isolate("I02"), "picker home I01 cannot reach I02"),
    ("isolated relocation buffer", _isolate("N_REL_BUFFER"), "cannot reach N_REL_BUFFER"),
    ("two packers one station", _packer_coverage, "PK01 has 2 packers"),
    ("missing packer", _missing_packer, "PK01 has 0 packers"),
    ("service wrong bay", _wrong_service_node, "must be on the aisle axis"),
    ("service ignores rack geometry", _wrong_rack_geometry, "must be on the aisle axis"),
    ("feed cargo role", _segment_role("FEED01", "parcel"), "FEED01 cargo role must be tote"),
    ("branch cargo role", _segment_role("BRANCH01", "parcel"), "BRANCH01 cargo role must be tote"),
    ("loop cargo role", _segment_role("LOOP_E", "parcel"), "joins tote and parcel"),
    (
        "outfeed cargo role",
        _segment_role("OUTFEED01", "tote"),
        "OUTFEED01 cargo role must be parcel",
    ),
    ("main cargo role", _segment_role("OUT_MAIN", "tote"), "OUT_MAIN cargo role must be parcel"),
    ("conveyor speed", _config_value("conveyor_speed_mps", 2), "conveyor timing"),
    ("conveyor tick", _config_value("conveyor_tick_s", 2), "conveyor timing"),
    ("conveyor cell", _config_value("conveyor_cell_m", 2), "conveyor timing"),
    ("buffer capacity", _config_value("pack_buffer_capacity", 5), "buffer_capacity differs"),
    ("conveyor dead end", _remove_connection("FEED01"), "is a dead end"),
    ("unreachable pack", _remove_connection("BRANCH01"), "PK01 is not reachable"),
    ("unreachable shipping", _unreachable_shipping, "outfeed PK01: SHIPPING is not reachable"),
    ("exitless conveyor cycle", _exitless_cycle, "cannot reach any exit"),
    ("tote pool 95", _config_value("totes_total", 95), "exactly 96"),
    ("tote pool 97", _config_value("totes_total", 97), "exactly 96"),
    ("port source start", _port_endpoint(True), "valid cell boundary"),
    ("port destination end", _port_endpoint(False), "valid cell boundary"),
]
CASES += [
    (
        f"rack size {axis} {value}",
        _rack_size(axis, value),
        "size components must be strictly positive",
    )
    for axis in range(3)
    for value in (0.0, -1.0)
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


@pytest.mark.parametrize("target", ["PK01", "SHIPPING"])
def test_topology_rejects_duplicate_exit_targets(contracts_dir: Path, target: str) -> None:
    raw = _load(contracts_dir, "layout.example.json")
    raw["pack_stations"][1]["pack_id"] = target
    with pytest.raises(TopologyError, match="duplicate exit target"):
        ConveyorTopology.from_layout(Layout.from_data(raw))


@pytest.mark.parametrize(
    ("start", "end"),
    [("NOPE", "NOPE"), ("NOPE", "BRANCH01:1"), ("FEED01:0", "NOPE")],
)
def test_travel_cells_rejects_unknown_cells(layout: Layout, start: str, end: str) -> None:
    with pytest.raises(TopologyError, match="unknown conveyor cell"):
        ConveyorTopology.from_layout(layout).travel_cells(start, end)


def _copy_contracts(contracts_dir: Path, destination: Path) -> None:
    for path in contracts_dir.glob("*.json"):
        (destination / path.name).write_bytes(path.read_bytes())


@pytest.mark.parametrize("filename", ["layout.example.json", "simulation_defaults.json"])
@pytest.mark.parametrize("token", ["1.00000000000000001", "1e-999", "1e999", "9007199254740993"])
def test_loader_rejects_inexact_number_tokens(
    contracts_dir: Path, tmp_path: Path, filename: str, token: str
) -> None:
    _copy_contracts(contracts_dir, tmp_path)
    path = tmp_path / filename
    raw = _load(contracts_dir, filename)
    if filename == "layout.example.json":
        raw["conveyor"]["segments"][0]["length_m"] = "NUMBER_TOKEN"
    else:
        raw["walk_speed_mps"] = "NUMBER_TOKEN"
    path.write_text(json.dumps(raw).replace('"NUMBER_TOKEN"', token), encoding="utf-8")
    with pytest.raises(ContractError, match="cannot be reconstructed exactly"):
        load_contract_bundle(tmp_path)


def test_from_json_text_rejects_inexact_number_tokens(contracts_dir: Path) -> None:
    raw = _load(contracts_dir, "simulation_defaults.json")
    raw["walk_speed_mps"] = "NUMBER_TOKEN"
    text = json.dumps(raw).replace('"NUMBER_TOKEN"', "1.00000000000000001")
    with pytest.raises(ValueError, match="cannot be reconstructed exactly"):
        SimulationConfig.from_json_text(text)


@pytest.mark.parametrize("token", ["1.2000", "12e-1", "0.1"])
def test_exact_numbers_preserve_decimal_value(contracts_dir: Path, token: str) -> None:
    raw = _load(contracts_dir, "simulation_defaults.json")
    raw["walk_speed_mps"] = "NUMBER_TOKEN"
    text = json.dumps(raw).replace('"NUMBER_TOKEN"', token)
    config = SimulationConfig.from_json_text(text)
    assert exact(config.walk_speed_mps) == Fraction(token)


def test_from_data_rejects_inexact_integer(contracts_dir: Path) -> None:
    raw = _load(contracts_dir, "simulation_defaults.json")
    raw["walk_speed_mps"] = 9007199254740993
    with pytest.raises(ValueError, match="cannot be reconstructed exactly"):
        SimulationConfig.from_data(raw)


@pytest.mark.parametrize("field", ["open_pallet_count", "relocation_worker_count"])
@pytest.mark.parametrize("value", [True, 1.0])
def test_config_integer_literals_reject_bool_and_float(
    contracts_dir: Path, tmp_path: Path, field: str, value: bool | float
) -> None:
    raw = _load(contracts_dir, "simulation_defaults.json")
    raw[field] = value
    with pytest.raises(ValidationError, match="requires an integer literal"):
        SimulationConfig.from_data(raw)
    _copy_contracts(contracts_dir, tmp_path)
    (tmp_path / "simulation_defaults.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ContractError, match="requires an integer literal"):
        load_contract_bundle(tmp_path)


def test_cli_reports_semantic_issues_before_compiling_paths(
    contracts_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli import main

    _copy_contracts(contracts_dir, tmp_path)
    raw = _load(contracts_dir, "layout.example.json")
    _set_edge_node(raw, {}, {})
    (tmp_path / "layout.example.json").write_text(json.dumps(raw), encoding="utf-8")
    assert main(["validate-contracts", "--contracts-dir", str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert any("unknown node" in issue for issue in report["issues"])
