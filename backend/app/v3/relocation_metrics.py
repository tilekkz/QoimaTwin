"""N1 transfer costs are a labelled subset of the same physical workers' paid time."""

from app.v3.coordinator_metrics import summary as common_summary
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorSnapshot
from app.v3.interface import Json
from app.v3.relocation_models import RelocationProfile
from app.v3.relocation_observe import RelocationSnapshot

METRICS_VERSION = "qoima-manual-relocation-metrics-v1"


def _paid(outcome: CoordinatorOutcome, jobs: set[str], tick: int) -> int:
    total = 0
    for event in outcome.events:
        operation = event.operation
        if event.kind != "operation_started" or event.order_id not in jobs or operation is None:
            continue
        total += max(0, min(tick, operation.planned_end_tick) - operation.start_tick)
    return total


def _window(
    profile: RelocationProfile, outcome: CoordinatorOutcome, snapshot: CoordinatorSnapshot
) -> Json:
    jobs = {job.job_id: job for job in profile.jobs}
    if jobs and type(snapshot) is not RelocationSnapshot:
        raise ValueError("Relocation metrics require explicit relocation observations")
    views = snapshot.relocations if isinstance(snapshot, RelocationSnapshot) else ()
    if len(views) != len(jobs) or {view.job_id for view in views} != set(jobs):
        raise ValueError("Relocation metric job identities differ")
    offered = sum(job.arrival_tick <= snapshot.tick for job in jobs.values())
    placed = [view for view in views if view.placed_tick is not None]
    returned = sum(view.returned_tick is not None for view in views)
    units: dict[str, int] = {}
    for token in profile.coordinator.world.receipts.flow.stock.units:
        units[token.origin_hu] = units.get(token.origin_hu, 0) + 1
    return {
        "tick": snapshot.tick,
        "offered_jobs": offered,
        "admitted_jobs": sum(view.admitted_tick is not None for view in views),
        "placed_hus": len(placed),
        "placed_units": sum(units[jobs[view.job_id].hu_id] for view in placed),
        "returned_jobs": returned,
        "pending_placement": offered - len(placed),
        "pending_return": offered - returned,
        "paid_ticks": _paid(outcome, set(jobs), snapshot.tick),
    }


def summary(profile: RelocationProfile, outcome: CoordinatorOutcome) -> Json:
    return {
        "metrics_version": METRICS_VERSION,
        "counts_boundary": "settled_tick_inclusive",
        "integral_window": "[0,T)",
        "paid_ticks_scope": "subset_of_common_worker_labor_do_not_add",
        "common": common_summary(profile.coordinator, outcome),
        "at_horizon": _window(profile, outcome, outcome.at_horizon),
        "at_end": _window(profile, outcome, outcome.at_end),
    }
