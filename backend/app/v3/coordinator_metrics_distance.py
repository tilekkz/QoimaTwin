"""Paid observed route distance, including capped travel and actual effective role."""

from fractions import Fraction

from app.v3.coordinator_metrics_observed_values import elapsed, no_overlap, rational
from app.v3.coordinator_metrics_work import _role
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.interface import Json
from app.v3.light_flow_models import FlowOperation


def _operations(
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
    actors: set[str],
) -> list[tuple[str, FlowOperation, int]]:
    result: list[tuple[str, FlowOperation, int]] = []
    intervals: dict[str, list[tuple[int, int]]] = {actor: [] for actor in actors}
    for event in outcome.events:
        op = event.operation
        if event.kind != "operation_started" or op is None or event.tick >= point.tick:
            continue
        if event.actor_id not in actors or op.start_tick != event.tick:
            raise ValueError("KPI travel requires an actual known actor/start")
        actor = str(event.actor_id)
        duration = elapsed(op.start_tick, op.planned_end_tick, point.tick)
        if op.planned_end_tick <= op.start_tick:
            raise ValueError("KPI paid operation duration must be positive")
        intervals[actor].append((op.start_tick, op.start_tick + duration))
        if op.route is None:
            continue
        length = op.route.length_m
        if type(length) is not Fraction or length < 0:
            raise ValueError("KPI route requires nonnegative exact length")
        result.append((actor, op, duration))
    for values in intervals.values():
        no_overlap(values)
    return result


def distances(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> Json:
    actors = {a.actor_id for a in profile.world.receipts.flow.actors}
    primary = {a.actor_id: a.primary_role for a in profile.registry.workers}
    totals = dict.fromkeys(actors, Fraction(0))
    carts = dict.fromkeys(actors, Fraction(0))
    roles: dict[str, Fraction] = {}
    for actor, op, duration in _operations(outcome, point, actors):
        if op.route is None:
            raise ValueError("KPI travel route missing after classification")
        length = op.route.length_m
        observed = length * Fraction(duration, op.planned_end_tick - op.start_tick)
        totals[actor] += observed
        carts[actor] += observed if op.cart_id is not None else 0
        role = _role(profile, point, actor, op.start_tick)
        roles[role] = roles.get(role, Fraction(0)) + observed
    return {
        "progress_policy": "linear_over_actual_quantized_operation_interval",
        "total_paid_distance_m": rational(sum(totals.values(), Fraction(0))),
        "by_effective_role_m": {key: rational(value) for key, value in sorted(roles.items())},
        "actors": [
            {
                "actor_id": actor,
                "primary_role": primary[actor],
                "paid_distance_m": rational(totals[actor]),
                "cart_push_distance_m": rational(carts[actor]),
            }
            for actor in sorted(actors)
        ],
    }
