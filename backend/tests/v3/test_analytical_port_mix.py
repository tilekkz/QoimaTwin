"""F1 literal hand oracle from adaptive-v3 brief section8; no engine-derived numbers."""

from fractions import Fraction as F

import pytest

from app.v3.analytical_port_mix import PortMixFixture, compare_placements, score_placement


def fixture() -> PortMixFixture:
    return PortMixFixture(
        slot_port_distances_m=((F(120), F(168), F(144)), (F(168), F(120), F(144))),
        sku_port_moves=((72, 18, 10), (18, 72, 10)),
    )


def test_f1_fixed_port_mix_swap_worsens_by_5184_metres() -> None:
    inputs = fixture()
    result = compare_placements(inputs, (0, 1), (1, 0))
    assert result.baseline_m == 26_208
    assert result.candidate_m == 31_392
    assert result.candidate_minus_baseline_m == 5_184
    assert result.source_kind == "analytical_fixture"
    assert result.metric == "weighted_route_metres"
    assert inputs == fixture()  # compare does not retune the common inputs


def test_f1_opposite_predeclared_mix_reverses_preference() -> None:
    original = fixture()
    opposite = PortMixFixture(original.slot_port_distances_m, ((18, 72, 10), (72, 18, 10)))
    result = compare_placements(opposite, (0, 1), (1, 0))
    assert (result.baseline_m, result.candidate_m) == (F(31_392), F(26_208))
    assert result.candidate_minus_baseline_m == -5_184


def test_f1_noop_and_zero_demand_remain_zero_gain() -> None:
    inputs = fixture()
    assert compare_placements(inputs, (0, 1), (0, 1)).candidate_minus_baseline_m == 0
    empty = PortMixFixture(inputs.slot_port_distances_m, ((0, 0, 0), (0, 0, 0)))
    assert score_placement(empty, (0, 1)) == 0


@pytest.mark.parametrize("placement", [(0,), (0, 0), (0, 2), (0, -1), (0, True)])
def test_f1_rejects_invalid_or_colliding_assignment(placement: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        score_placement(fixture(), placement)


@pytest.mark.parametrize("moves", [((-1, 2, 3),), ((True, 2, 3),), ((1, 2),)])
def test_f1_rejects_invalid_move_counts(moves: tuple[tuple[int, ...], ...]) -> None:
    with pytest.raises(ValueError):
        PortMixFixture(fixture().slot_port_distances_m, moves)


def test_f1_rejects_negative_distance() -> None:
    with pytest.raises(ValueError):
        PortMixFixture(((F(-1),),), ((1,),))
