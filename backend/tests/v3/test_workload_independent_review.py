"""Independent arithmetic, calendar, identity and no-stock-credit checks."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.workload_allocation import allocate_quotas
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import BurstWindow, DemandWeight, WorkloadPolicy
from app.v3.workload_policy import arrival_ticks
from tests.v3.test_workload_fixtures import hand_source


def test_joint_hamilton_quota_preserves_exact_rounding_debt() -> None:
    quotas = allocate_quotas((DemandWeight("A", "P", F(1)), DemandWeight("B", "P", F(2))), 2)
    assert [(q.expected, q.count, q.delta) for q in quotas] == [
        (F(2, 3), 1, F(1, 3)),
        (F(4, 3), 1, F(-1, 3)),
    ]
    assert sum(q.delta for q in quotas) == 0


def test_joint_ties_are_sku_then_port_and_zero_share_never_receives_remainder() -> None:
    rows = (
        DemandWeight("B", "A", F(1)),
        DemandWeight("A", "Z", F(1)),
        DemandWeight("B", "Z", F(0)),
        DemandWeight("A", "A", F(1)),
    )
    quotas = allocate_quotas(rows, 2)
    assert {(q.sku_id, q.port_id): q.count for q in quotas} == {
        ("A", "A"): 1,
        ("A", "Z"): 1,
        ("B", "A"): 0,
        ("B", "Z"): 0,
    }
    assert quotas == allocate_quotas(tuple(reversed(rows)), 2)


def test_twelve_equal_burst_windows_use_numeric_chronological_ties() -> None:
    windows = tuple(BurstWindow(i * 10, i * 10 + 1, F(1)) for i in range(12))
    policy = WorkloadPolicy(120, 10, 0, "burst", windows)
    assert arrival_ticks(policy, 10) == tuple(range(0, 100, 10))


def test_offers_never_reuse_initial_stock_even_when_demand_exceeds_stock() -> None:
    source = hand_source()
    value = materialize_workload(source, WorkloadPolicy(7, 10, 20, "normal"))
    inbound = [job for job in value.jobs if job.direction == "inbound"]
    outbound = [job for job in value.jobs if job.direction == "outbound"]
    initial_ids = {hu for template in source.templates for hu in template.initial_hu_ids}
    assert len(inbound) == 10 and len(outbound) == 20
    assert len({job.hu_id for job in inbound}) == 10
    assert not initial_ids.intersection(job.hu_id for job in inbound)
    assert all(job.hu_id is None and job.lot_id is None for job in outbound)
    assert all(0 <= job.arrival_tick < 7 for job in value.jobs)
    assert source == hand_source() and not value.operational_admission


def test_calendar_and_source_permutations_do_not_redraw_population() -> None:
    source = hand_source()
    normal = materialize_workload(source, WorkloadPolicy(100, 4, 4, "normal"))
    reordered = replace(
        source,
        templates=source.templates[::-1],
        inbound_weights=source.inbound_weights[::-1],
        outbound_weights=source.outbound_weights[::-1],
    )
    assert (
        normal.to_dict()
        == materialize_workload(
            reordered,
            WorkloadPolicy(100, 4, 4, "normal"),
        ).to_dict()
    )
    burst = materialize_workload(
        source,
        WorkloadPolicy(100, 4, 4, "burst", (BurstWindow(20, 21, F(1)),)),
    )
    assert normal.population_id == burst.population_id
    assert normal.workload_id != burst.workload_id
    before = {job.job_id: replace(job, arrival_tick=0) for job in normal.jobs}
    after = {job.job_id: replace(job, arrival_tick=0) for job in burst.jobs}
    assert before == after and {job.arrival_tick for job in burst.jobs} == {20}


@pytest.mark.parametrize("count", [0, 1, 2, 7, 19])
def test_normal_half_open_clock_exact_integer_formula(count: int) -> None:
    policy = WorkloadPolicy(7, count, count, "normal")
    ticks = arrival_ticks(policy, count)
    assert ticks == tuple(i * 7 // count for i in range(count))
    assert all(0 <= tick < 7 for tick in ticks)


def test_zero_budget_retains_complete_source_without_fabricated_jobs() -> None:
    source = hand_source()
    result = materialize_workload(source, WorkloadPolicy(1, 0, 0, "normal"))
    assert result.jobs == () and result.source == source
    assert all(q.count == 0 and q.expected == q.delta == 0 for q in result.inbound_quotas)
