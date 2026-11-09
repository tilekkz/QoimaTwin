"""Exact deterministic identities for pure whole-HU allocation hand cases."""

from app.v3.adaptation_authority import require_same_authority
from app.v3.outbound_stock_models import StockHU
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import TimedWorkload
from app.v3.workload_validation import name


def verify_workload(workload: TimedWorkload) -> None:
    if type(workload) is not TimedWorkload:
        raise ValueError("Exact TimedWorkload required")
    expected = materialize_workload(workload.source, workload.policy)
    require_same_authority(workload, expected)


def unit_ids(hu_id: str, quantity: int) -> tuple[str, ...]:
    return tuple(f"{hu_id}:unit:{ordinal:04d}" for ordinal in range(1, quantity + 1))


def receipt_declarations(workload: TimedWorkload) -> tuple[StockHU, ...]:
    templates = {template.sku_id: template for template in workload.source.templates}
    result: list[StockHU] = []
    for job in workload.jobs:
        if job.direction != "inbound":
            continue
        if job.hu_id is None or job.lot_id is None:
            raise ValueError("Inbound offer must declare its exact HU and lot")
        template = templates[job.sku_id]
        result.append(
            StockHU(
                job.hu_id,
                job.sku_id,
                job.archetype_id,
                job.lot_id,
                unit_ids(job.hu_id, job.quantity_units),
                job.quantity_units,
                template.gross_mass_kg,
                None,
                job.job_id,
                job.arrival_tick,
            )
        )
    return tuple(result)


def verify_original(workload: TimedWorkload, original: tuple[StockHU, ...]) -> None:
    if type(original) is not tuple or any(type(hu) is not StockHU for hu in original):
        raise ValueError("Exact original StockHU tuple required")
    by_id = {name(hu.hu_id): hu for hu in original}
    expected_ids = {hu for t in workload.source.templates for hu in t.initial_hu_ids}
    if len(by_id) != len(original) or set(by_id) != expected_ids:
        raise ValueError("Every original HU must occur exactly once")
    for template in workload.source.templates:
        for hu_id in template.initial_hu_ids:
            actual = by_id[hu_id]
            name(actual.initial_owner_id)
            expected = StockHU(
                hu_id,
                template.sku_id,
                template.archetype_id,
                template.source_lot_id,
                unit_ids(hu_id, template.quantity_units),
                template.quantity_units,
                template.gross_mass_kg,
                actual.initial_owner_id,
                None,
                None,
            )
            require_same_authority(actual, expected)


def verify_pools(
    workload: TimedWorkload,
    original: tuple[StockHU, ...],
    incoming: tuple[StockHU, ...],
) -> None:
    verify_workload(workload)
    verify_original(workload, original)
    require_same_authority(incoming, receipt_declarations(workload))
    combined = (*original, *incoming)
    if len({hu.hu_id for hu in combined}) != len(combined):
        raise ValueError("Original and declared incoming HU identities must be disjoint")
    tokens = [token for hu in combined for token in hu.unit_ids]
    if len(set(tokens)) != len(tokens):
        raise ValueError("Unit identities must be globally unique")
