"""Population identity is independent of its explicit synthetic arrival calendar."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction as F

import pytest

from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import BurstWindow, WorkloadPolicy
from tests.v3.test_workload_fixtures import hand_source


def test_normal_and_burst_change_only_times_and_workload_identity() -> None:
    source = hand_source()
    normal = WorkloadPolicy(10, 4, 4, "normal")
    peak = replace(
        normal, calendar="burst", windows=(BurstWindow(2, 4, F(1)), BurstWindow(7, 8, F(1)))
    )
    first, second = materialize_workload(source, normal), materialize_workload(source, peak)
    assert first.population_id == second.population_id and first.workload_id != second.workload_id
    assert {j.job_id: replace(j, arrival_tick=0) for j in first.jobs} == {
        j.job_id: replace(j, arrival_tick=0) for j in second.jobs
    }
    assert sorted(j.arrival_tick for j in first.jobs if j.direction == "inbound") == [0, 2, 5, 7]
    assert sorted(j.arrival_tick for j in second.jobs if j.direction == "inbound") == [2, 3, 7, 7]
    assert first.source == source and not first.operational_admission


def test_whole_hu_offers_are_new_but_outbound_stock_is_not_fabricated() -> None:
    result = materialize_workload(hand_source(), WorkloadPolicy(10, 2, 2, "normal"))
    incoming = [job for job in result.jobs if job.direction == "inbound"]
    outgoing = [job for job in result.jobs if job.direction == "outbound"]
    assert len({job.hu_id for job in incoming}) == 2
    assert all(job.hu_id and job.lot_id for job in incoming)
    assert all(job.hu_id is None and job.lot_id is None for job in outgoing)
    assert all(job.quantity_units == 24 for job in result.jobs)
    assert len({job.job_id for job in result.jobs}) == 4


def test_materialization_is_immutable_order_independent_and_hash_canonical() -> None:
    source, policy = hand_source(), WorkloadPolicy(10, 3, 3, "normal")
    first = materialize_workload(source, policy)
    permuted = replace(
        source, templates=source.templates[::-1], inbound_weights=source.inbound_weights[::-1]
    )
    assert first.to_dict() == materialize_workload(permuted, policy).to_dict()
    value = first.to_dict()
    identifier = value.pop("workload_id")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    assert hashlib.sha256(raw).hexdigest() == identifier
    value["jobs"].clear()
    assert len(first.jobs) == 6
    with pytest.raises(FrozenInstanceError):
        first.jobs[0].arrival_tick = 9  # type: ignore[misc]


def test_zero_offers_keep_source_catalog_without_creating_stock() -> None:
    result = materialize_workload(hand_source(), WorkloadPolicy(10, 0, 0, "normal"))
    assert result.jobs == () and len(result.source.templates) == 2
    assert all(q.count == 0 for q in (*result.inbound_quotas, *result.outbound_quotas))
