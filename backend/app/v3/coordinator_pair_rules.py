"""Explicit scenario and physical sameness gates, independent of performance outcomes."""

from dataclasses import replace
from typing import cast

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_pair_models import (
    IncomparableCoordinatorPair,
    PairScenario,
    UnsupportedPairScenario,
)
from app.v3.flow_profile_wire import record


def scenario_name(value: object) -> PairScenario:
    if type(value) is not str or value not in {"N0", "N4"}:
        raise UnsupportedPairScenario("UNSUPPORTED_PAIRED_SCENARIO: only bounded N0/N4")
    return cast(PairScenario, value)


def require_same_materialized_world(
    baseline: CoordinatorProfile,
    candidate: CoordinatorProfile,
) -> None:
    left = canonical_bytes(record(replace(baseline, intents=())))
    right = canonical_bytes(record(replace(candidate, intents=())))
    if left != right:
        raise IncomparableCoordinatorPair("MATERIALIZED_PHYSICAL_INPUT_DRIFT")


def require_scenario_plan(
    baseline: CoordinatorProfile,
    candidate: CoordinatorProfile,
    scenario: PairScenario,
) -> None:
    if scenario == "N0":
        return
    if baseline.intents:
        raise IncomparableCoordinatorPair("N4_BASELINE_ROLE_PLAN_MUST_BE_EMPTY")
    intents = candidate.intents
    workers = {worker.actor_id: worker for worker in candidate.registry.workers}
    if (
        len(intents) != 2
        or len({intent.actor_id for intent in intents}) != 2
        or len({intent.station_id for intent in intents}) != 2
        or any(intent.actor_id not in workers for intent in intents)
        or any(workers[i.actor_id].primary_role != "pick" for i in intents)
        or any("pack" not in workers[i.actor_id].eligible_roles for i in intents)
    ):
        raise IncomparableCoordinatorPair("N4_REQUIRES_TWO_DISTINCT_PICKER_HELPERS")
    actors = {actor.actor_id: actor for actor in candidate.world.receipts.flow.actors}
    if any(i.actor_id not in actors or i.restore_node != actors[i.actor_id].home for i in intents):
        raise IncomparableCoordinatorPair("N4_REQUIRES_RETURN_TO_EXISTING_ACTOR_HOME")
