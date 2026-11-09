"""L08 source topology and resource oracles; no simulation-derived expectations."""

import json
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from app.v3.conveyor_source import load_conveyor_source
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle


@pytest.fixture(scope="module")
def bundle() -> V3Bundle:
    return load_v3_bundle(Path("data/v3-proposal"))


def test_source_counts_and_distinct_resource_semantics(bundle: V3Bundle) -> None:
    source = load_conveyor_source(bundle)
    assert (len(source.nodes), len(source.edges), len(source.cells)) == (34, 45, 90)
    assert (len(source.resources), len(source.stations), source.module_count) == (15, 6, 87)
    memberships = Counter(c for r in source.resources.values() for c in r.cell_ids)
    assert memberships == Counter({key: 1 for key in source.cells})
    assert (source.resources["V3_MAIN"].capacity, source.resources["V3_MAIN"].exclusive) == (
        67,
        False,
    )
    assert len(source.resources["V3_CURVE_EXCLUSIVE"].cell_ids) == 4
    assert source.resources["V3_CURVE_EXCLUSIVE"].capacity == 1
    assert source.resources["V3_SPUR01"].exclusive
    assert len(source.resources["V3_SPUR01"].cell_ids) == 2
    arc = source.edges["v3:conv:entry-arc"].arc
    assert arc is not None and arc.radius_m == Fraction("1.25")
    assert arc.centre == (Fraction("128.5"), Fraction(".92"), Fraction("4.25"))
    assert source.cells["V3-C-ARC-00"].theta_range == (Fraction(0), Fraction("-.39269908169872414"))
    assert source.cells["V3-C-ARC-00"].position is None


def test_graph_connectivity_and_frozen_catalog(bundle: V3Bundle) -> None:
    source = load_conveyor_source(bundle)
    for station in source.stations.values():
        assert source.reachable("v3:conv:intake", station.work_node_id)
        assert source.reachable(station.work_node_id, "v3:conv:output")
    assert not source.reachable("v3:conv:PK01:WORK", "v3:conv:PK06:WORK")
    with pytest.raises(ValueError, match="Unknown"):
        source.reachable("missing", "v3:conv:output")
    with pytest.raises(TypeError):
        source.cells["ghost"] = source.cells[next(iter(source.cells))]  # type: ignore[index]
    assert len(source.document_sha256) == len(source.raw_sha256) == 64
    assert source.source_revision == bundle.source_revision


@pytest.mark.parametrize("defect", ["edge_node", "edge_resource", "cell", "station", "duplicate"])
def test_corrupt_source_references_reject(bundle: V3Bundle, defect: str) -> None:
    from app.v3.conveyor_source import decode_conveyor_document

    raw = load_conveyor_source(bundle).document.decode()
    if defect == "edge_node":
        raw["edges"][0]["to_node_id"] = "missing"
    elif defect == "edge_resource":
        raw["edges"][0]["resource_id"] = "missing"
    elif defect == "cell":
        raw["resources"][0]["member_cell_ids"][0] = "missing"
    elif defect == "station":
        raw["packing_stations"][0]["spur_resource_id"] = "missing"
    else:
        raw["nodes"].append(raw["nodes"][0])
    with pytest.raises(ValueError):
        decode_conveyor_document(raw)


def test_changed_bundle_revision_rejects(bundle: V3Bundle) -> None:
    with pytest.raises(ValueError):
        load_conveyor_source(replace(bundle, source_revision="unknown"))


@pytest.mark.parametrize("defect", ["bytes", "manifest", "missing"])
def test_separate_supplement_pin_rejects_tampering(
    bundle: V3Bundle, tmp_path: Path, defect: str
) -> None:
    source = Path("data/v3-conveyor-proposal")
    for name in ("conveyor-v3.json", "provenance.json"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    if defect == "bytes":
        target = tmp_path / "conveyor-v3.json"
        target.write_bytes(target.read_bytes().replace(b"0.55", b"0.65", 1))
    elif defect == "manifest":
        target = tmp_path / "provenance.json"
        data = json.loads(target.read_bytes())
        data["raw_sha256"] = "a" * 64
        target.write_text(json.dumps(data), encoding="utf-8")
    else:
        (tmp_path / "conveyor-v3.json").unlink()
    with pytest.raises(ValueError):
        load_conveyor_source(bundle, tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("resource_type", "unknown"),
        ("capacity", 68),
        ("per_cell_capacity", 2),
    ],
)
def test_no_new_resource_semantics_are_silently_invented(
    bundle: V3Bundle, field: str, value: str | int
) -> None:
    from app.v3.conveyor_source import decode_conveyor_document

    raw = load_conveyor_source(bundle).document.decode()
    raw["resources"][0][field] = value
    with pytest.raises(ValueError):
        decode_conveyor_document(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("turn_timing", "during_edge"),
        ("turn_at_node_id", "v3:conv:PK01:B"),
        ("requires_turn_dwell_s", 0),
        ("requires_turn_dwell_s", True),
        ("path_kind", "teleport"),
        ("length_m", -1),
    ],
)
def test_bad_edge_geometry_and_turn_semantics_fail_closed(
    bundle: V3Bundle, field: str, value: str | int | bool
) -> None:
    from app.v3.conveyor_source import decode_conveyor_document

    raw = load_conveyor_source(bundle).document.decode()
    edge = next(e for e in raw["edges"] if e["edge_id"] == "v3:conv:PK01:divert")
    edge[field] = value
    with pytest.raises(ValueError):
        decode_conveyor_document(raw)
