"""Bounded original-first allocation; source authentication is a separate public seam."""

from collections import defaultdict, deque

from app.v3.outbound_stock_models import StockAllocation, StockHU
from app.v3.outbound_stock_validation import receipt_declarations, verify_pools, verify_workload
from app.v3.workload_models import TimedWorkload, WorkloadJob


def declared_receipts(workload: TimedWorkload) -> tuple[StockHU, ...]:
    """Declare future ancestry only; creates neither UnitToken nor StockLedger credit."""
    verify_workload(workload)
    return receipt_declarations(workload)


def _row(offer: WorkloadJob, hu: StockHU | None) -> StockAllocation:
    if hu is None:
        return StockAllocation(offer, "unallocated", None, "DECLARED_STOCK_EXHAUSTED", None)
    if hu.receipt_job_id is None:
        return StockAllocation(offer, "original_bound", hu, None, None)
    if hu.receipt_arrival_tick is None:
        raise ValueError("Receipt dependency must retain its offered arrival")
    return StockAllocation(
        offer,
        "receipt_dependency",
        hu,
        None,
        hu.receipt_arrival_tick > offer.arrival_tick,
    )


def allocate_offers(
    workload: TimedWorkload,
    original: tuple[StockHU, ...],
    incoming: tuple[StockHU, ...],
) -> tuple[StockAllocation, ...]:
    """Pure allocation helper; arbitrary hand sources do not establish source authority."""
    verify_pools(workload, original, incoming)
    pools: dict[str, deque[StockHU]] = defaultdict(deque)
    ordered = (
        *sorted(original, key=lambda hu: hu.hu_id),
        *sorted(incoming, key=lambda hu: (hu.receipt_arrival_tick, hu.receipt_job_id)),
    )
    for hu in ordered:
        pools[hu.sku_id].append(hu)
    return tuple(
        _row(job, pools[job.sku_id].popleft() if pools[job.sku_id] else None)
        for job in workload.jobs
        if job.direction == "outbound"
    )
