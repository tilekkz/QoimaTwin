"""Offline checks against the committed immutable base and vehicle supplement."""

from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.vehicle_admission import check_handling_prerequisites
from app.v3.vehicle_evidence import HandlingRequest
from app.v3.vehicle_package import load_repository_vehicle_adapter
from app.v3.vehicle_source import VehicleAdapter

DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def source_adapter() -> VehicleAdapter:
    return load_repository_vehicle_adapter(DATA / "v3-proposal", DATA / "v3-vehicle-proposal")


def test_pinned_source_counts_and_static_limits_are_reproducible_offline(
    source_adapter: VehicleAdapter,
) -> None:
    assert (len(source_adapter.graph.nodes), len(source_adapter.graph.arcs)) == (620, 1316)
    assert len(source_adapter.graph.resources) == 44 + 282
    assert len(source_adapter.handling.slots) == 776
    assert sum(slot.blocked for slot in source_adapter.handling.slots) == 188
    assert sum(len(port[2]) for port in source_adapter.handling.ports) == 17
    loads = {load.cargo_id: load for load in source_adapter.handling.loads}
    assert loads["PALLET_LOAD"].hu_mass_kg == 455
    assert loads["PALLET_LOAD"].extended_arm_m == 1
    assert loads["LONG_BUNDLE"].hu_mass_kg + loads["LONG_BUNDLE"].attachment_mass_kg == 240


def test_actual_local_reverse_and_traffic_are_not_erased(source_adapter: VehicleAdapter) -> None:
    prefix = "v3:module:HEAVY_E:001:B1:vehicle:segment:000:"
    forward = source_adapter.graph.arcs[prefix + "f"]
    reverse = source_adapter.graph.arcs[prefix + "r"]
    assert forward.motion_direction == 1 and reverse.motion_direction == -1
    assert forward.geometry.start_yaw_rad == reverse.geometry.start_yaw_rad
    assert forward.source == reverse.target and forward.target == reverse.source
    assert forward.source_groups == ()
    assert forward.clear_width_m is None
    assert forward.traffic_groups == (
        "v3:traffic:cell:29:04",
        "v3:traffic:cell:30:04",
        "v3:traffic:cell:30:05",
        "v3:traffic:cell:30:06",
        "v3:traffic:cell:30:07",
        "v3:traffic:cell:30:08",
        "v3:traffic:cell:30:09",
    )


def test_actual_pallet_candidate_needs_evidence_despite_geometric_fit(
    source_adapter: VehicleAdapter,
) -> None:
    request = HandlingRequest(
        "new-explicit-HU",
        "PALLET_LOAD",
        "INBOUND_FORKLIFT_PAIR",
        "IN_W_BULK",
        "v3:slot:HEAVY_E:001:L1:B1",
        "place",
        (F("1.2"), F("1.35"), F(1)),
        F(455),
        F(".18"),
        (),
    )
    verdict = check_handling_prerequisites(
        source_adapter.handling, request, source_adapter.source_hashes
    )
    assert verdict.design_passed and not verdict.evidence_complete
    assert not verdict.operational_admission


def test_modified_supplement_manifest_is_not_accepted(tmp_path: Path) -> None:
    supplement = tmp_path / "supplement"
    supplement.mkdir()
    (supplement / "provenance.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA256"):
        load_repository_vehicle_adapter(DATA / "v3-proposal", supplement)
