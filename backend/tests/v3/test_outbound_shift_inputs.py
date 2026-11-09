"""Canonical authority guards and caller clocks, with no runtime invocation."""

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction as F
from typing import Any, cast

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.outbound_shift_inputs import (
    compile_outbound_shift,
    load_outbound_shift_inputs,
    verify_outbound_shift_inputs,
)
from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.workload_models import WorkloadPolicy
from tests.v3.test_outbound_shift_fixtures import ADAPTATION, BASE, POLICY, compiled

__all__ = ["compiled"]


def test_materialized_once_deterministic_and_not_operational(compiled: OutboundShiftInputs) -> None:
    repeated = compile_outbound_shift(BASE, ADAPTATION, POLICY)
    restored = load_outbound_shift_inputs(compiled.frozen_bytes)
    fresh = verify_outbound_shift_inputs(compiled)
    assert restored == repeated == fresh == compiled
    assert fresh is not compiled and fresh.scenario is not compiled.scenario
    assert fresh.workload is not compiled.workload
    jobs = compiled.workload.jobs
    assert len(jobs) == 10
    assert sorted(j.arrival_tick for j in jobs if j.direction == "outbound") == [
        0,
        14,
        28,
        43,
        57,
        72,
        86,
    ]
    assert sorted(j.arrival_tick for j in jobs if j.direction == "inbound") == [0, 33, 67]
    assert len(compiled.workload.outbound_quotas) == len(
        compiled.scenario.postshift.outbound_weights
    )
    assert any(q.count == 0 for q in compiled.workload.outbound_quotas)
    wire = parse_json(compiled.frozen_bytes)
    assert wire["operational_admission"] is False and wire["full_n1_acceptance"] is False
    assert canonical_bytes(wire["workload"]) == compiled.workload_bytes
    assert canonical_bytes(wire["scenario"]) == compiled.scenario_bytes
    assert canonical_bytes(wire["choices"]) == compiled.policy_bytes


@pytest.mark.parametrize("bad", [True, 101.0, F(101)])
def test_exact_policy_clock_required(bad: Any) -> None:
    policy = WorkloadPolicy(bad, 3, 7, "normal")
    with pytest.raises(ValueError):
        compile_outbound_shift(BASE, ADAPTATION, policy)


@pytest.mark.parametrize("field", ["extra", "version", "clock", "source", "weight", "arrival"])
def test_rehashed_wire_cannot_change_authoritative_or_materialized_facts(
    compiled: OutboundShiftInputs,
    field: str,
) -> None:
    wire = parse_json(compiled.frozen_bytes)
    if field == "extra":
        wire["extra"] = 1
    elif field == "version":
        wire["schema_version"] = "foreign"
    elif field == "clock":
        wire["workload"]["clock"]["ticks_per_second"] = 1000
    elif field == "source":
        wire["scenario"]["raw_sources"][0]["raw"] += " "
    elif field == "weight":
        wire["scenario"]["postshift"]["weights"]["outbound"][0]["weight"] = [999, 1]
    else:
        wire["workload"]["jobs"][0]["arrival_tick"] += 1
    with pytest.raises(ValueError):
        load_outbound_shift_inputs(canonical_bytes(wire))


def test_retained_type_alias_weights_and_foreign_clock_fail(compiled: OutboundShiftInputs) -> None:
    original = compiled.scenario.postshift
    changed = replace(original.outbound_weights[0], weight=F(999))
    source = replace(original, outbound_weights=(changed, *original.outbound_weights[1:]))
    scenario = replace(compiled.scenario, postshift=source)
    with pytest.raises(ValueError):
        verify_outbound_shift_inputs(replace(compiled, scenario=scenario))
    with pytest.raises(ValueError):
        verify_outbound_shift_inputs(replace(compiled, policy=replace(POLICY, horizon_tick=102)))
    job = replace(compiled.workload.jobs[0], arrival_tick=cast(int, False))
    workload = replace(compiled.workload, jobs=(job, *compiled.workload.jobs[1:]))
    with pytest.raises(ValueError):
        verify_outbound_shift_inputs(replace(compiled, workload=workload))


def test_immutable_values_and_strict_json(compiled: OutboundShiftInputs) -> None:
    with pytest.raises(FrozenInstanceError):
        cast(Any, compiled.scenario).legacy_scenario_id = "N1"
    for raw in (compiled.frozen_bytes + b" ", b'{"choices":{},"choices":{}}'):
        with pytest.raises(ValueError):
            load_outbound_shift_inputs(raw)
