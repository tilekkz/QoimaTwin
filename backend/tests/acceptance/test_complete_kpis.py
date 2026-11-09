"""Spec 01 section 10 KPIs with arithmetic independent of engine output."""

from pathlib import Path
from typing import Any, cast

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from app.simulation.metrics_summary import summary
from tests.builders import fixture_order, receipt, run_inputs, scenario

pytestmark = pytest.mark.acceptance


def _run(bundle: ContractBundle, contracts_dir: Path, horizon: float) -> dict[str, Any]:
    engine = Engine(
        run_inputs(bundle, contracts_dir, scenario([fixture_order()], horizon_s=horizon)),
        check_invariants=True,
    )
    return cast(dict[str, Any], summary(engine, engine.run()))


def test_executed_picker_distance_is_clipped_inside_first_edge(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    result = _run(bundle, contracts_dir, 2)
    horizon, end = result["at_horizon"], result["at_end"]
    assert horizon["admitted_total"] == 1
    assert horizon["picked_total"] == 0
    picker = horizon["picker_metrics"]["P01"]
    assert picker["distance_m"] == pytest.approx(2 * 1.2)
    assert picker["travel_s"] == 2
    assert picker["service_s"] == 0
    assert end["picker_metrics"]["P01"]["distance_m"] == 21
    assert end["picker_metrics"]["P01"]["travel_s"] == 17.5
    assert end["picker_metrics"]["P01"]["service_s"] == 12.3 + 3
    assert horizon["total_active_labor_s"] == 2
    # Fixture travel(6+8+10)/2=12; spec/defaults pickup15+drop15=30.
    # Picker32.8 + pack24.1 + scan8 + F02(12+30) =106.9 active labor seconds.
    assert end["total_active_labor_s"] == pytest.approx(106.9)
    assert end["labor_by_role"]["forklift_driver"]["active_s"] == 42
    assert end["blocking"]["induction_s"] == 0.2
    assert end["blocking"]["pack_output_s"] == 0.9


def test_picked_and_inventory_use_their_own_cutoff(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    result = _run(bundle, contracts_dir, 30)
    horizon, end = result["at_horizon"], result["at_end"]
    # Last pick: (4+8.5)/1.2 + 2*6.15 = 22.71666... <30; handoff ends32.8.
    assert horizon["picked_total"] == 1
    assert horizon["admitted_wip"] == 1
    assert end["admitted_wip"] == 0
    assert horizon["packed_total"] == 0
    for sku in ("FIXTURE_01", "FIXTURE_02"):
        assert horizon["inventory_balance"][sku]["tote"] == 1
        assert horizon["inventory_balance"][sku]["dispatched"] == 0
        assert end["inventory_balance"][sku]["tote"] == 0
        assert end["inventory_balance"][sku]["dispatched"] == 1


def test_station_tote_and_belt_kpis_use_time_integrals(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    horizon = _run(bundle, contracts_dir, 60)["at_horizon"]
    station = horizon["station_metrics"]["PK01"]
    assert station["started_total"] == 1
    assert station["packed_total"] == 0
    assert station["service_s"] == 8  # PACK [52,76.1), clipped at60.
    assert station["utilization"]["active"] == 8 / 60
    assert station["queue_mean"] == 0
    assert station["reserved_wip_mean"] == pytest.approx((60 - 32.8) / 60)
    assert station["reserved_wip_max"] == 1
    assert horizon["tote_metrics"]["free_mean"] == 95
    assert horizon["tote_metrics"]["free_min"] == 95
    assert horizon["tote_metrics"]["unavailable_s"] == 0
    # One tote is on physical cells on [33,52), hence 19 cell-seconds.
    assert horizon["conveyor_metrics"]["occupied_cells_mean"] == 19 / 60
    assert horizon["conveyor_metrics"]["jam_duration_s"] == 0


def test_receiving_area_is_distinct_from_waiting_queue(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = Engine(
        run_inputs(bundle, contracts_dir, scenario([], [receipt(0)], horizon_s=200)),
        check_invariants=True,
    )
    horizon = cast(dict[str, Any], summary(engine, engine.run()))["at_horizon"]
    # Arrival90; service ends180; pickup at180+6/2+15=198 releases area position.
    assert horizon["receiving_metrics"]["area_mean"] == 108 / 200
    assert horizon["queue_mean"]["receiving"] == 0
    assert horizon["receiving_metrics"]["accepted_total"] == 1
    assert horizon["receiving_metrics"]["putaway_total"] == 0  # putaway224 >H.
    assert engine.receiving.staging_physical_full_since_tick is None


def test_inventory_at_exact_horizon_excludes_the_boundary_transfer(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    horizon = _run(bundle, contracts_dir, 52)["at_horizon"]
    for sku in ("FIXTURE_01", "FIXTURE_02"):
        assert horizon["inventory_balance"][sku]["tote"] == 1
        assert horizon["inventory_balance"][sku]["pack_wip"] == 0


def test_staging_reservation_full_and_physical_full_are_distinct(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = Engine(
        run_inputs(bundle, contracts_dir, scenario([], [receipt(0)]), reserve_staging_capacity=1),
        check_invariants=True,
    )
    result = cast(dict[str, Any], summary(engine, engine.run()))
    limits = result["receiving_limits"]
    assert limits["staging_reservations_full_since_s"] == 180
    assert limits["staging_physical_full_since_s"] == 224
