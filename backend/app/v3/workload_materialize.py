"""Pure deterministic whole-HU offers; no engine, RNG, admission or stock mutation."""

from dataclasses import replace
from fractions import Fraction

from app.storage.canonical_json import sha256_hex
from app.v3.workload_allocation import allocate_quotas
from app.v3.workload_models import (
    Direction,
    Quota,
    TimedWorkload,
    WholeHUTemplate,
    WorkloadJob,
    WorkloadPolicy,
    WorkloadSource,
)
from app.v3.workload_policy import arrival_ticks, validate_policy
from app.v3.workload_validation import validate_workload_source
from app.v3.workload_wire import (
    MATERIALIZER_VERSION,
    STOCK_BINDING,
    source_dict,
    template_dict,
    workload_dict,
)


def _job(
    template: WholeHUTemplate,
    quota: Quota,
    ordinal: int,
    direction: Direction,
    population_id: str,
    tick: int,
) -> WorkloadJob:
    identifier = sha256_hex(
        {
            "population_id": population_id,
            "direction": direction,
            "sku_id": quota.sku_id,
            "port_id": quota.port_id,
            "ordinal": ordinal,
        }
    )
    inbound = direction == "inbound"
    return WorkloadJob(
        "v3:workload:job:" + identifier,
        direction,
        template.sku_id,
        template.archetype_id,
        sha256_hex(template_dict(template)),
        quota.port_id,
        template.quantity_units,
        tick,
        "v3:workload:hu:" + identifier if inbound else None,
        "v3:workload:lot:" + population_id + ":" + template.sku_id if inbound else None,
    )


def _direction_jobs(
    source: WorkloadSource,
    policy: WorkloadPolicy,
    quotas: tuple[Quota, ...],
    direction: Direction,
    population_id: str,
) -> tuple[WorkloadJob, ...]:
    templates = {template.sku_id: template for template in source.templates}
    slots = sorted(
        (Fraction(2 * ordinal + 1, 2 * quota.count), quota.sku_id, quota.port_id, ordinal)
        for quota in quotas
        for ordinal in range(quota.count)
    )
    by_pair = {(quota.sku_id, quota.port_id): quota for quota in quotas}
    ticks = arrival_ticks(policy, len(slots))
    return tuple(
        _job(templates[sku], by_pair[sku, port], ordinal, direction, population_id, tick)
        for (_, sku, port, ordinal), tick in zip(slots, ticks, strict=True)
    )


def materialize_workload(source: WorkloadSource, policy: WorkloadPolicy) -> TimedWorkload:
    validate_workload_source(source)
    validate_policy(policy)
    inbound = allocate_quotas(source.inbound_weights, policy.inbound_hus)
    outbound = allocate_quotas(source.outbound_weights, policy.outbound_hus)
    population_id = sha256_hex(
        {
            "materializer_version": MATERIALIZER_VERSION,
            "stock_binding": STOCK_BINDING,
            "source": source_dict(source),
            "offered_hus": {"inbound": policy.inbound_hus, "outbound": policy.outbound_hus},
        }
    )
    jobs = (
        *_direction_jobs(source, policy, inbound, "inbound", population_id),
        *_direction_jobs(source, policy, outbound, "outbound", population_id),
    )
    result = TimedWorkload(
        source,
        policy,
        inbound,
        outbound,
        tuple(sorted(jobs, key=lambda job: (job.arrival_tick, job.direction, job.job_id))),
        population_id,
        "",
    )
    return replace(result, workload_id=sha256_hex(workload_dict(result, include_id=False)))
