"""Exact C11 planning comparison (proxy route-seconds per unclocked horizon, never hours).

Expected Fractions come from an independent source-only recomputation (Claude subagent,
2026-11-08) using only layout-links arc `length_m`, adaptation-input move weights and
`cost_assumptions` (walk 1.4 m/s manual_cart, vehicle 1.8 m/s forklift_assisted), never
C11 reported floats or adapter output.
"""

from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.adaptation_compare import C11PlanningSet, load_c11_planning

BACKEND = Path(__file__).parents[2]
H1 = F(62612001870721576523387, 315000000000000000)
EXPECTED = {
    2: (F(6949993515160037189067, 17500000000000000), F(132296879684031043, 600000000000000)),
    4: (F(7804085204555041858931, 9843750000000000), F(1785363392927093521, 1800000000000000)),
    8: (F(7804085204555041858931, 4921875000000000), F(1785363392927093521, 1800000000000000)),
}
NET = {
    2: F(54664606728367345993, 315000000000000000),
    4: F(134947447787575080527, 105000000000000000),
    8: F(1122123280487691849337, 315000000000000000),
}


@pytest.fixture(scope="module")
def planning() -> C11PlanningSet:
    return load_c11_planning(BACKEND / "data/v3-adaptation-proposal", BACKEND / "data/v3-proposal")


@pytest.mark.parametrize("periods", [True, 1.0, F(1), 0, 3, "1"])
def test_result_horizon_rejects_aliases_and_unsupported_periods(
    planning: C11PlanningSet, periods: Any
) -> None:
    with pytest.raises(ValueError):
        planning.horizon(periods)


def test_one_period_is_a_legitimate_noop(planning: C11PlanningSet) -> None:
    result = planning.horizon(1)
    assert result.no_op and result.transfers == ()
    assert result.baseline_proxy_s == result.adapted_proxy_s == H1
    assert result.relocation_proxy_s == result.net_proxy_s == 0


@pytest.mark.parametrize("periods", [2, 4, 8])
def test_sensitivity_horizons_recompute_exact_proxy_terms(
    planning: C11PlanningSet, periods: int
) -> None:
    result = planning.horizon(periods)
    adapted, relocation = EXPECTED[periods]
    assert result.baseline_proxy_s == periods * H1
    assert (result.adapted_proxy_s, result.relocation_proxy_s) == (adapted, relocation)
    assert result.net_proxy_s == NET[periods] > 0
    assert all(t.net_proxy_s > 0 for t in result.transfers)
    reported = result.reported
    assert abs(reported.net_transport_cost_reduction_s - float(NET[periods])) < 1e-6
    assert result.period_unit == "unclocked_planning_period"
    assert (result.actual_engine_run, result.operational_admission) == (False, False)


def test_h2_transfer_terms_match_hand_recomputation(planning: C11PlanningSet) -> None:
    first, second = planning.horizon(2).transfers
    assert (first.sequence, first.transport_tag) == (1, "manual_cart")
    assert first.relocation_proxy_s == F(136142857142857151, 10**15)
    assert first.gross_proxy_s == F(67000000000000029, 437500000000000)
    assert second.relocation_proxy_s == F(126527913495791881, 1500000000000000)
    assert second.gross_proxy_s == F(338752091796801887, 1406250000000000)
    assert second.released_by_sequence == 1  # destination freed by the first planned move


def test_result_is_deterministic_and_inventory_is_conserved(planning: C11PlanningSet) -> None:
    again = load_c11_planning(BACKEND / "data/v3-adaptation-proposal", BACKEND / "data/v3-proposal")
    assert canonical_bytes(planning.as_json()) == canonical_bytes(again.as_json())
    for periods in (1, 2, 4, 8):
        inventory = planning.horizon(periods).inventory
        assert (inventory.handling_units, inventory.units) == (530, 12256)
        assert inventory.gross_mass_kg == F(188077, 20)
    data = planning.as_json()
    assert data["actual_engine_run"] is False and data["operational_admission"] is False
    assert data["comparison_inputs_sha256_verified"] is False
