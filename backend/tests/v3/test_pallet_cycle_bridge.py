"""Each paid 5cm connection needs its own directed source arc and geometry proof."""

from dataclasses import replace
from fractions import Fraction as F
from types import MappingProxyType

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_bridge import validate_bridge_source
from app.v3.pallet_cycle_engine import PalletCycleEngine
from app.v3.pallet_cycle_types import PhysicalPallet
from app.v3.vehicle_package import load_repository_vehicle_adapter
from app.v3.vehicle_source import VehicleAdapter
from tests.v3.test_pallet_cycle_clock import SOURCE, timing
from tests.v3.test_pallet_cycle_engine import job
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture

ARC = "v3:module:HEAVY_E:001:B1:vehicle:segment:002:"


@pytest.fixture(scope="module")
def source() -> VehicleAdapter:
    return load_repository_vehicle_adapter(
        SOURCE.parent / "v3-proposal", SOURCE.parent / "v3-vehicle-proposal"
    )


def test_original_source_coordinates_define_exact_5cm_distance(source: VehicleAdapter) -> None:
    binding = validate_bridge_source(source)
    assert binding.distance_m == F(1, 20)
    assert binding.prehandle_xyz == (F(604, 5), F(0), F(35, 2))
    assert binding.action_start_xyz == (F(2417, 20), F(0), F(35, 2))
    assert binding.entry_arc_id == ARC + "r"
    assert binding.exit_arc_id == ARC + "f"
    assert binding.entry_fraction[0] == 0
    assert binding.exit_fraction[1] == 1


@pytest.mark.parametrize("direction", ["r", "f"])
def test_no_implicit_reverse_arc_is_invented(source: VehicleAdapter, direction: str) -> None:
    arcs = dict(source.graph.arcs)
    del arcs[ARC + direction]
    altered = replace(source, graph=replace(source.graph, arcs=MappingProxyType(arcs)))
    with pytest.raises(ValueError, match="directed"):
        validate_bridge_source(altered)


def test_return_arc_requires_the_actual_driver_vehicle_pair(source: VehicleAdapter) -> None:
    arcs = dict(source.graph.arcs)
    arcs[ARC + "f"] = replace(
        arcs[ARC + "f"], equipment_pairs=frozenset({"OUTBOUND_FORKLIFT_PAIR"})
    )
    altered = replace(source, graph=replace(source.graph, arcs=MappingProxyType(arcs)))
    with pytest.raises(ValueError, match="pair"):
        validate_bridge_source(altered)


def test_actual_two_bridges_are_paid_and_preserve_base_proof(proven: LocalGeometryProof) -> None:
    pallet = PhysicalPallet("physical-PALLET-1", "PALLET_LOAD", 24, F(455), proven.mesh_sha256)
    engine = PalletCycleEngine(timing(), (job("A"),), pallet, SOURCE, proven, source_approach=True)
    result = engine.run(20_000_000, 30_000_000)
    assert result.at_end.tick == 13_800_000
    assert result.geometry_proof == proven
    assert len(result.geometry_proof.segments) == 13
    assert result.bridge is not None
    assert result.bridge.entry_cover_checks > 0 and result.bridge.exit_cover_checks > 0
    moves = [
        e.operation
        for e in result.events
        if e.kind == "operation_started"
        and e.operation is not None
        and e.operation.operation.kind == "bridge"
    ]
    assert [m.planned_end_tick - m.started_tick for m in moves] == [50_000, 50_000]
    assert [m.operation.source_arc_id for m in moves] == [ARC + "r", ARC + "f"]
    assert result.at_end.observed_pose.root_z == F(-1)
