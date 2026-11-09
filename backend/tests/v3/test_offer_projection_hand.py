"""Independent fixed-budget arithmetic without pretending a hand source is C10."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.offer_projection_materialize import materialize_projection
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.workload_models import BurstWindow, DemandWeight, WorkloadPolicy
from tests.v3.test_workload_fixtures import hand_source

PORTS = {"OUT1": frozenset({"SMALL_CARTON"}), "OUT2": frozenset({"SMALL_CARTON"})}


def choices(budget: int = 4) -> OfferProjectionChoices:
    return OfferProjectionChoices(
        WorkloadPolicy(4_000_000, 0, budget, "normal"),
        "explicit",
        (
            DemandWeight("A", "OUT1", F(1)),
            DemandWeight("A", "OUT2", F(0)),
            DemandWeight("B", "OUT1", F(0)),
            DemandWeight("B", "OUT2", F(1)),
        ),
    )


def test_one_to_three_budget_four_has_exact_quotas_and_one_second_spacing() -> None:
    source = hand_source()
    result = materialize_projection(source, (("A", F(1)), ("B", F(3))), choices(), PORTS, "a" * 64)
    assert [(q.sku_id, q.port_id, q.count) for q in result.quotas] == [
        ("A", "OUT1", 1),
        ("A", "OUT2", 0),
        ("B", "OUT1", 0),
        ("B", "OUT2", 3),
    ]
    assert [job.arrival_tick for job in result.jobs] == [0, 1_000_000, 2_000_000, 3_000_000]
    assert [job.sku_id for job in result.jobs] == ["B", "A", "B", "B"]
    assert all(q.delta == 0 for q in result.quotas)
    assert all(job.job_id.startswith("v3:offer-projection:job:") for job in result.jobs)
    assert all(job.hu_id is None and job.lot_id is None for job in result.jobs)
    assert source == hand_source()


def test_all_zero_zero_budget_is_empty_without_dummy_weights() -> None:
    result = materialize_projection(
        hand_source(), (("A", F(0)), ("B", F(0))), choices(0), PORTS, "a" * 64
    )
    assert result.jobs == ()
    assert len(result.quotas) == len(result.weights) == len(result.port_mix) == 4
    assert all(q.count == q.expected == q.delta == 0 for q in result.quotas)
    assert all(w.weight == 0 for w in result.weights)
    with pytest.raises(ValueError, match=r"positive|POSITIVE"):
        materialize_projection(
            hand_source(), (("A", F(0)), ("B", F(0))), choices(1), PORTS, "a" * 64
        )


def test_source_c10_choice_keeps_mix_and_exposes_permitted_zero_pairs() -> None:
    choice = OfferProjectionChoices(choices().policy, "source_c10", ())
    result = materialize_projection(
        hand_source(), (("A", F(1)), ("B", F(3))), choice, PORTS, "a" * 64
    )
    assert result.port_mix == choices().port_mix
    assert sum(q.count for q in result.quotas) == 4


def test_hamilton_fractional_tie_and_burst_calendar_are_explicit() -> None:
    policy = WorkloadPolicy(4_000_000, 0, 3, "burst", (BurstWindow(1_000_000, 4_000_000, F(1)),))
    result = materialize_projection(
        hand_source(),
        (("A", F(1, 3)), ("B", F(1, 3))),
        replace(choices(), policy=policy),
        PORTS,
        "a" * 64,
    )
    positive = [q for q in result.quotas if q.expected]
    assert [(q.count, q.expected, q.delta) for q in positive] == [
        (2, F(3, 2), F(1, 2)),
        (1, F(3, 2), F(-1, 2)),
    ]
    assert [j.arrival_tick for j in result.jobs] == [1_000_000, 2_000_000, 3_000_000]


@pytest.mark.parametrize(
    "predictions",
    [
        (("A", F(1)),),
        (("A", F(1)), ("A", F(3))),
        (("A", F(1)), ("X", F(3))),
        (("A", 1), ("B", F(3))),
        (("A", True), ("B", F(3))),
        (("A", F(-1)), ("B", F(3))),
        [["A", F(1)], ["B", F(3)]],
    ],
)
def test_predictions_require_exact_complete_nonnegative_signal(predictions: Any) -> None:
    with pytest.raises(ValueError):
        materialize_projection(hand_source(), predictions, choices(), PORTS, "a" * 64)


def test_explicit_mix_requires_every_permitted_pair_and_normalized_shares() -> None:
    original = choices()
    variants = (
        original.port_mix[:-1],
        (replace(original.port_mix[0], weight=F(2)), *original.port_mix[1:]),
        (replace(original.port_mix[0], port_id="IN1"), *original.port_mix[1:]),
        (replace(original.port_mix[0], weight=1), *original.port_mix[1:]),  # type: ignore[arg-type]
    )
    for mix in variants:
        with pytest.raises(ValueError):
            materialize_projection(
                hand_source(),
                (("A", F(1)), ("B", F(3))),
                replace(original, port_mix=mix),
                PORTS,
                "a" * 64,
            )


def test_nonempty_inbound_budget_is_rejected_and_never_silently_removed() -> None:
    with pytest.raises(ValueError, match="INBOUND"):
        materialize_projection(
            hand_source(),
            (("A", F(1)), ("B", F(3))),
            replace(choices(), policy=WorkloadPolicy(4_000_000, 1, 4, "normal")),
            PORTS,
            "a" * 64,
        )


def test_wrong_source_grant_and_foreign_forecast_hash_fail() -> None:
    for ports, identity in (({"OUT1": frozenset()}, "a" * 64), (PORTS, "wrong")):
        with pytest.raises(ValueError):
            materialize_projection(
                hand_source(), (("A", F(1)), ("B", F(3))), choices(), ports, identity
            )


def test_population_identity_binds_forecast_and_preserves_choice_order_invariance() -> None:
    args = (hand_source(), (("A", F(1)), ("B", F(3))))
    first = materialize_projection(*args, choices(), PORTS, "a" * 64)
    shuffled = replace(choices(), port_mix=tuple(reversed(choices().port_mix)))
    assert materialize_projection(*args, shuffled, PORTS, "a" * 64) == first
    changed = materialize_projection(*args, choices(), PORTS, "b" * 64)
    assert changed.population_id != first.population_id
    assert {j.job_id for j in changed.jobs}.isdisjoint(j.job_id for j in first.jobs)
