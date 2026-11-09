"""Hamilton composition and explicit calendar, without altering source demand authority."""

from collections.abc import Mapping
from fractions import Fraction

from app.storage.canonical_json import sha256_hex
from app.v3.flow_profile_wire import record
from app.v3.offer_projection_models import VERSION, OfferProjectionChoices, ProjectionOffers
from app.v3.offer_projection_validation import resolve_mix, validate_choices, validate_predictions
from app.v3.workload_allocation import allocate_quotas
from app.v3.workload_models import DemandWeight, Quota, WorkloadJob, WorkloadPolicy, WorkloadSource
from app.v3.workload_policy import arrival_ticks
from app.v3.workload_validation import digest, validate_workload_source
from app.v3.workload_wire import source_dict, template_dict


def _jobs(
    source: WorkloadSource,
    quotas: tuple[Quota, ...],
    policy: WorkloadPolicy,
    population_id: str,
) -> tuple[WorkloadJob, ...]:
    templates = {t.sku_id: t for t in source.templates}
    slots = sorted(
        (Fraction(2 * ordinal + 1, 2 * q.count), q.sku_id, q.port_id, ordinal)
        for q in quotas
        for ordinal in range(q.count)
    )
    result = []
    for (_, sku, port, ordinal), tick in zip(slots, arrival_ticks(policy, len(slots)), strict=True):
        template = templates[sku]
        identifier = sha256_hex(
            {"population_id": population_id, "sku_id": sku, "port_id": port, "ordinal": ordinal}
        )
        result.append(
            WorkloadJob(
                "v3:offer-projection:job:" + identifier,
                "outbound",
                sku,
                template.archetype_id,
                sha256_hex(template_dict(template)),
                port,
                template.quantity_units,
                tick,
                None,
                None,
            )
        )
    return tuple(sorted(result, key=lambda job: (job.arrival_tick, job.direction, job.job_id)))


def materialize_projection(
    source: WorkloadSource,
    predictions: tuple[tuple[str, Fraction], ...],
    choices: OfferProjectionChoices,
    permitted_ports: Mapping[str, frozenset[str]],
    forecast_id: str,
) -> ProjectionOffers:
    """Analytical seam; public compilation separately authenticates forecast and source."""
    validate_workload_source(source)
    validate_choices(choices)
    digest(forecast_id)
    signal = validate_predictions(predictions, source)
    mix = resolve_mix(source, choices, permitted_ports)
    weights = tuple(DemandWeight(r.sku_id, r.port_id, signal[r.sku_id] * r.weight) for r in mix)
    quotas = allocate_quotas(weights, choices.policy.outbound_hus)
    population_id = sha256_hex(
        {
            "version": VERSION,
            "forecast_id": forecast_id,
            "source": source_dict(source),
            "port_mix": record(mix),
            "weights": record(weights),
            "outbound_budget": choices.policy.outbound_hus,
        }
    )
    return ProjectionOffers(
        mix, weights, quotas, _jobs(source, quotas, choices.policy, population_id), population_id
    )
