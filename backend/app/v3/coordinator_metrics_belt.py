"""Observed carrier occupancy and stopped exposure; leases are not body occupancy."""

from app.v3.coordinator_metrics_observed_values import elapsed, unavailable
from app.v3.coordinator_metrics_values import integer, ratio
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorSnapshot
from app.v3.interface import Json


def belt(outcome: CoordinatorOutcome, point: CoordinatorSnapshot) -> Json:
    admitted: dict[str, int] = {}
    completed: dict[str, int] = {}
    for outer in outcome.events:
        event = outer.belt_event
        if event is None or outer.tick > point.tick:
            continue
        if event.tick != outer.tick:
            raise ValueError("KPI belt event differs from shared clock")
        if event.kind == "admitted":
            if event.job_id in admitted:
                raise ValueError("KPI duplicate belt admission")
            admitted[event.job_id] = integer(event.tick)
        elif event.kind == "completed":
            if event.job_id not in admitted or event.job_id in completed:
                raise ValueError("KPI belt completion without unique admission")
            completed[event.job_id] = integer(event.tick)
    active = set(admitted) - set(completed)
    actual = {
        c.job_id
        for c in point.belt.carriers
        if c.status not in {"outside", "unreleased", "complete"}
    }
    if active != actual or len(completed) != point.belt.completed:
        raise ValueError("KPI belt journal and captured carrier state differ")
    area = sum(elapsed(start, completed.get(key), point.tick) for key, start in admitted.items())
    stopped = integer(point.belt.queue_ticks)
    if stopped > area:
        raise ValueError("KPI stopped carrier exposure exceeds admitted exposure")
    return {
        "admitted_carrier_ticks": area,
        "mean_admitted_carriers": ratio(area, point.tick),
        "current_admitted_carriers": len(active),
        "stopped_carrier_ticks": stopped,
        "mean_stopped_carriers": ratio(stopped, point.tick),
        "stopped_scope": "native_wait_counter_including_paid_output_pickup",
        "current_body_occupied_cells": len(
            {cell for c in point.belt.carriers for cell in c.occupied_cells}
        ),
        "physical_cell_occupancy_integral": unavailable("No continuous body-cell crossing journal"),
        "blockage_by_cause": unavailable("Native stopped counter does not classify every cause"),
    }
