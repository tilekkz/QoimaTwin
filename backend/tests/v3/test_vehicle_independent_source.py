"""Actual source pin and hand reverse-route oracles; no vehicle execution."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.vehicle_admission import check_handling_prerequisites
from app.v3.vehicle_evidence import HandlingRequest
from app.v3.vehicle_geometry import pose_at
from app.v3.vehicle_graph import decode_vehicle_graph
from app.v3.vehicle_package import load_repository_vehicle_adapter
from app.v3.vehicle_source import VehicleAdapter, load_vehicle_adapter
from tests.v3.test_vehicle_fixtures import graph_documents


@pytest.fixture(scope="module")
def adapter() -> VehicleAdapter:
    backend = Path(__file__).resolve().parents[2]
    return load_repository_vehicle_adapter(
        backend / "data/v3-proposal", backend / "data/v3-vehicle-proposal"
    )


def test_actual_pallet_local_route_preserves_cargo_pair_and_traffic(
    adapter: VehicleAdapter,
) -> None:
    identifier = "v3:module:HEAVY_E:001:B1:vehicle:segment:000:f"
    arc = adapter.graph.arcs[identifier]
    assert adapter.declared_loaded_arc(identifier, "PALLET_LOAD", "INBOUND_FORKLIFT_PAIR")
    assert adapter.declared_loaded_arc(identifier, "PALLET_LOAD", "OUTBOUND_FORKLIFT_PAIR")
    assert not adapter.declared_loaded_arc(identifier, "LONG_BUNDLE", "INBOUND_FORKLIFT_PAIR")
    assert not adapter.declared_loaded_arc(identifier, "SMALL_CARTON", "INBOUND_FORKLIFT_PAIR")
    assert not adapter.declared_loaded_arc(identifier, "PALLET_LOAD", "imaginary")
    assert arc.clear_width_m is None
    assert arc.source_groups == ()
    assert len(arc.traffic_groups) == 7
    assert arc.arc_id in adapter.graph.route_bindings[arc.source_ref]


def test_real_source_candidate_has_no_operational_or_actual_evidence_grant(
    adapter: VehicleAdapter,
) -> None:
    load = next(load for load in adapter.handling.loads if load.cargo_id == "PALLET_LOAD")
    value = HandlingRequest(
        "new-HU",
        "PALLET_LOAD",
        "INBOUND_FORKLIFT_PAIR",
        "IN_W_BULK",
        "v3:slot:HEAVY_E:001:L1:B1",
        "place",
        load.dimensions_m,
        F(455),
        F(".18"),
        (),
    )
    result = check_handling_prerequisites(adapter.handling, value, adapter.source_hashes)
    assert result.design_passed
    assert not result.evidence_complete
    assert not result.operational_admission
    assert result.requires_actual_mesh_verifier
    wrong_pair = replace(value, pair_id="OUTBOUND_FORKLIFT_PAIR")
    assert not check_handling_prerequisites(
        adapter.handling, wrong_pair, adapter.source_hashes
    ).design_passed


def test_valid_json_whitespace_change_still_breaks_exact_source_pin(
    adapter: VehicleAdapter, tmp_path: Path
) -> None:
    folder = tmp_path / "docs/v3/contract-proposals"
    folder.mkdir(parents=True)
    for name, raw in adapter.raw_documents.items():
        suffix = b" " if name == "vehicle-handling-v3.json" else b""
        (folder / name).write_bytes(raw + suffix)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_vehicle_adapter(tmp_path)


def test_hand_reverse_route_keeps_chassis_yaw_and_shared_resources() -> None:
    documents = graph_documents()
    arc = documents["layout"]["vehicle_graph"]["arcs"][0]
    arc.update(from_node_id="B", to_node_id="A", motion_direction=-1)
    arc["geometry"].update(front_axle_start_xz_m=[0, 2.4], front_axle_end_xz_m=[0, 0.4])
    graph = decode_vehicle_graph(documents["layout"], documents["traffic"], documents["vehicle"])
    reverse = graph.arcs["AB"]
    middle = pose_at(reverse.geometry, F(1, 2), graph.axle_offset_m)
    # pose_at intentionally returns floats; this is arithmetic roundoff, not clearance.
    assert middle.root_xyz == pytest.approx((0.0, 0.0, 1.0), abs=1e-14, rel=0)
    assert middle.front_axle_xyz == pytest.approx((0.0, 0.0, 1.4), abs=1e-14, rel=0)
    assert middle.yaw_rad == 0.0
    assert reverse.motion_direction == -1
    assert reverse.source_groups == ("junction",)
    assert reverse.traffic_groups == ("shared",)
