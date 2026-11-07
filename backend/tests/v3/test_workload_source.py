"""C10 planning-period arithmetic, never a source hourly throughput claim."""

from collections import Counter
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.inputs import load_v3_bundle
from app.v3.workload_allocation import allocate_quotas
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import WorkloadPolicy, WorkloadSource
from app.v3.workload_source import (
    expected_port_totals,
    load_workload_source,
    minimum_period_multiplier,
)


@pytest.fixture(scope="module")
def source() -> WorkloadSource:
    return load_workload_source(load_v3_bundle(Path("data/v3-proposal")))


def test_unclocked_source_port_weights_match_literal_c10_arithmetic(source: WorkloadSource) -> None:
    assert dict(expected_port_totals(source.inbound_weights)) == {
        "IN_E_PARCEL": F("957.6"),
        "IN_N_STANDARD": F("304.4"),
        "IN_W_BULK": F(238),
    }
    assert dict(expected_port_totals(source.outbound_weights)) == {
        "OUT_W_RETAIL": F("787.7"),
        "OUT_S_EXPRESS": F("560.7"),
        "OUT_E_B2B": F("151.6"),
    }
    for rows in (source.inbound_weights, source.outbound_weights):
        assert sum((row.weight for row in rows), F(0)) == 50 * (16 + 8 + 4 + 2)
    # STANDARD turnover2: inbound .7 gives7/5, outbound .45 gives9/10.
    assert minimum_period_multiplier(source.inbound_weights) == 5
    assert minimum_period_multiplier(source.outbound_weights) == 10
    assert minimum_period_multiplier((*source.inbound_weights, *source.outbound_weights)) == 10


def test_ten_period_population_preserves_every_sku_port_share_exactly(
    source: WorkloadSource,
) -> None:
    expectations = (
        (source.inbound_weights, {"IN_E_PARCEL": 9576, "IN_N_STANDARD": 3044, "IN_W_BULK": 2380}),
        (source.outbound_weights, {"OUT_W_RETAIL": 7877, "OUT_S_EXPRESS": 5607, "OUT_E_B2B": 1516}),
    )
    for rows, expected in expectations:
        quotas = allocate_quotas(rows, 15_000)
        totals: Counter[str] = Counter()
        for quota in quotas:
            totals[quota.port_id] += quota.count
            assert quota.delta == 0
        assert totals == expected and sum(totals.values()) == 15_000


def test_source_retains_all_templates_initial_hus_ports_and_fingerprints(
    source: WorkloadSource,
) -> None:
    assert len(source.templates) == 200
    assert len({hu for template in source.templates for hu in template.initial_hu_ids}) == 530
    assert len({template.archetype_id for template in source.templates}) == 8
    assert len(source.raw_fingerprints) == len(source.document_fingerprints) == 14
    # Explicit synthetic8h calendar, not an interpretation of C10's unclocked period.
    result = materialize_workload(source, WorkloadPolicy(28_800_000_000, 1500, 1500, "normal"))
    assert len(result.jobs) == 3000
    assert len({job.archetype_id for job in result.jobs}) == 8
    assert len({job.port_id for job in result.jobs}) == 6
    assert result.source == source and not result.operational_admission
    assert all(0 <= job.arrival_tick < 28_800_000_000 for job in result.jobs)
