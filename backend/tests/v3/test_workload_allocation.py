"""Hand arithmetic for whole-HU allocation; no engine-derived expectations."""

from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.workload_allocation import allocate_quotas
from app.v3.workload_models import DemandWeight


def test_largest_remainder_uses_exact_fractions() -> None:
    weights = (DemandWeight("A", "P", F(3)), DemandWeight("B", "P", F(1)))
    result = allocate_quotas(weights, 3)
    assert [(q.sku_id, q.port_id, q.count) for q in result] == [("A", "P", 2), ("B", "P", 1)]
    assert [q.expected for q in result] == [F(9, 4), F(3, 4)]
    assert [q.delta for q in result] == [F(-1, 4), F(1, 4)]


def test_ties_use_sku_then_port_and_ignore_input_order() -> None:
    weights = tuple(
        DemandWeight(sku, port, F(1)) for sku, port in (("B", "A"), ("A", "Z"), ("A", "A"))
    )
    result = allocate_quotas(weights, 1)
    assert result == allocate_quotas(tuple(reversed(weights)), 1)
    assert [(q.sku_id, q.port_id, q.count) for q in result] == [
        ("A", "A", 1),
        ("A", "Z", 0),
        ("B", "A", 0),
    ]


def test_zero_budget_preserves_all_zero_quotas() -> None:
    result = allocate_quotas((DemandWeight("A", "P", F(7, 10)),), 0)
    assert result[0].count == 0 and result[0].expected == result[0].delta == 0
    assert allocate_quotas((), 0) == ()


@pytest.mark.parametrize("budget", [True, -1, 1.0, float("nan"), float("inf")])
def test_non_integer_or_negative_budget_rejects(budget: object) -> None:
    with pytest.raises(ValueError):
        allocate_quotas((DemandWeight("A", "P", F(1)),), cast(int, budget))


def test_duplicate_pairs_and_positive_budget_without_weight_reject() -> None:
    row = DemandWeight("A", "P", F(1))
    with pytest.raises(ValueError):
        allocate_quotas((row, row), 1)
    with pytest.raises(ValueError):
        allocate_quotas((), 1)
