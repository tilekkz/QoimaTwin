"""Every base and relocation handling completion has exactly one prescribed stock effect."""

from app.v3.coordinator_run_effects import EFFECTS, EventFacts, _arrivals
from app.v3.light_flow_models import FlowEvent
from app.v3.relocation_models import RelocationProfile

ALL_EFFECTS = {
    **EFFECTS,
    "relocation_take": ("relocation_taken",),
    "relocation_place": ("relocation_placed",),
}


def validate_effects(
    profile: RelocationProfile, events: tuple[FlowEvent, ...], horizon: int, end: int
) -> None:
    facts = EventFacts(events)
    inverse = {effect: stage for stage, values in ALL_EFFECTS.items() for effect in values}
    for event in events:
        if event.kind in {*inverse, "package_prepared"} and event.delta is None:
            raise ValueError("Physical handover lacks its actual stock delta")
        if event.delta is not None:
            stage = inverse.get(event.kind)
            if event.kind == "package_prepared":
                facts.operation(event.order_id, "operation_started", "pack", event.tick)
            elif stage is None:
                raise ValueError("Stock delta has no declared handover kind")
            else:
                actual = facts.operation(event.order_id, "operation_completed", stage, event.tick)
                if event.actor_id is not None and event.actor_id != actual.actor_id:
                    raise ValueError("Stock effect actor differs from completed handling")
        if event.kind == "operation_completed" and event.operation is not None:
            for effect in ALL_EFFECTS.get(event.operation.kind, ()):
                if facts.one(event.order_id, effect, event.tick).delta is None:
                    raise ValueError("Completed handover lost its stock effect")
        if (
            event.kind == "operation_started"
            and event.operation is not None
            and event.operation.kind == "pack"
        ):
            facts.one(event.order_id, "package_prepared", event.tick)
    _arrivals(profile.coordinator, facts, events, horizon, end)
    _relocation_arrivals(profile, facts, events, horizon, end)


def _relocation_arrivals(
    profile: RelocationProfile,
    facts: EventFacts,
    events: tuple[FlowEvent, ...],
    horizon: int,
    end: int,
) -> None:
    jobs = {j.job_id: j for j in profile.jobs}
    for job in jobs.values():
        if job.arrival_tick <= end:
            facts.one(job.job_id, "relocation_arrived", job.arrival_tick)
    for event in events:
        if event.order_id not in jobs:
            continue
        job = jobs[event.order_id]
        if event.kind == "relocation_arrived" and event.tick != job.arrival_tick:
            raise ValueError("Relocation arrival changed its declared clock")
        if event.kind in {"relocation_admitted", "inventory_claim_acquired"}:
            if not job.arrival_tick <= event.tick < horizon:
                raise ValueError("Relocation admission is outside [arrival,H)")
            facts.one(job.job_id, "relocation_admitted", event.tick)
            facts.one(job.job_id, "inventory_claim_acquired", event.tick)
        if event.kind in {"inventory_claim_released", "relocation_returned"}:
            facts.one(job.job_id, "inventory_claim_released", event.tick)
            facts.one(job.job_id, "relocation_returned", event.tick)
