"""One materializer call and finite declared coverage, not runtime capability."""

from dataclasses import replace
from fractions import Fraction
from typing import Any, cast

import pytest

from app.v3 import outbound_shift_materialize
from app.v3.outbound_shift_inputs import compile_outbound_shift, verify_outbound_shift_inputs
from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import TimedWorkload, WorkloadPolicy, WorkloadSource
from tests.v3.test_outbound_shift_fixtures import ADAPTATION, BASE, POLICY, compiled

__all__ = ["compiled"]


def test_compiler_materializes_exactly_one_postshift_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = materialize_workload
    calls: list[tuple[WorkloadSource, WorkloadPolicy]] = []

    def counted(source: WorkloadSource, policy: WorkloadPolicy) -> TimedWorkload:
        calls.append((source, policy))
        return original(source, policy)

    monkeypatch.setattr(outbound_shift_materialize, "materialize_workload", counted)
    inputs = compile_outbound_shift(BASE, ADAPTATION, POLICY)
    assert calls == [(inputs.scenario.postshift, POLICY)]
    assert inputs.workload.source is inputs.scenario.postshift


def test_zero_offers_preserve_complete_scenario_and_zero_quotas() -> None:
    inputs = compile_outbound_shift(BASE, ADAPTATION, WorkloadPolicy(37, 0, 0, "normal"))
    assert inputs.workload.jobs == ()
    assert len(inputs.scenario.initial_placements) == 530
    assert len(inputs.workload.source.templates) == 200
    assert all(q.count == 0 for q in inputs.workload.outbound_quotas)
    assert {q.port_id for q in inputs.workload.outbound_quotas} == {
        "OUT_W_RETAIL",
        "OUT_S_EXPRESS",
        "OUT_E_B2B",
    }
    assert inputs.workload.outbound_quotas


def test_nonzero_b2b_offers_and_all_classes_are_not_filtered() -> None:
    inputs = compile_outbound_shift(BASE, ADAPTATION, WorkloadPolicy(1009, 0, 1500, "normal"))
    jobs = inputs.workload.jobs
    assert len(jobs) == 1500
    assert {job.port_id for job in jobs} == {"OUT_W_RETAIL", "OUT_S_EXPRESS", "OUT_E_B2B"}
    assert len({job.archetype_id for job in jobs}) == 8
    b2b = [job for job in jobs if job.port_id == "OUT_E_B2B"]
    assert b2b and {job.archetype_id for job in b2b} == {
        "HEAVY_BOX",
        "PALLET_LOAD",
        "IBC",
        "LONG_BUNDLE",
        "DRUM",
        "FRAGILE_CRATE",
    }
    assert all(job.hu_id is None and job.lot_id is None for job in jobs)
    assert sum(q.count for q in inputs.workload.outbound_quotas) == 1500
    assert sum((q.delta for q in inputs.workload.outbound_quotas), Fraction(0)) == 0


def test_numeric_equal_fraction_alias_is_not_source_authority(
    compiled: OutboundShiftInputs,
) -> None:
    source = compiled.scenario.postshift
    index = next(i for i, row in enumerate(source.outbound_weights) if row.weight.denominator == 1)
    rows = list(source.outbound_weights)
    rows[index] = replace(rows[index], weight=cast(Any, rows[index].weight.numerator))
    shifted = replace(source, outbound_weights=tuple(rows))
    assert shifted == source
    changed = replace(compiled, scenario=replace(compiled.scenario, postshift=shifted))
    with pytest.raises(ValueError):
        verify_outbound_shift_inputs(changed)
