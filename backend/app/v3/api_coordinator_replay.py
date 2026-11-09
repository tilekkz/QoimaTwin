"""Separate arbitrary settled-state reads preserve the existing captured-only endpoint."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import FastAPI, Query

from app.api.context import ApiContext
from app.api.models import ArtifactId
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile
from app.v3.api_coordinator_readers import _request_context
from app.v3.api_coordinator_registry import CoordinatorRegistry
from app.v3.api_coordinator_replay_projection import project_snapshot
from app.v3.coordinator_seek import _replay_context
from app.v3.interface import Json

READER_VERSION = "qoima-coordinator-settled-replay-api-0.1.0"
Tick = Annotated[str, Query(pattern=r"^(0|[1-9][0-9]*)$", max_length=20)]
Registration = Callable[[ApiContext, CoordinatorRegistry, str], Awaitable[FrozenCoordinatorProfile]]


def attach_replay_route(
    app: FastAPI,
    context: ApiContext,
    registry: CoordinatorRegistry,
    registered: Registration,
) -> None:
    @app.get("/api/v3/coordinator-runs/{run_id}/replay")
    async def get_replay(run_id: ArtifactId, tick: Tick) -> Json:
        frozen = await registered(context, registry, run_id)
        return await asyncio.to_thread(replay, context.store, run_id, int(tick), frozen)


def replay(
    store: ArtifactStore,
    identifier: str,
    tick: int,
    frozen: FrozenCoordinatorProfile,
) -> Json:
    context = _request_context(store, identifier, frozen)
    run = context.run()
    if type(tick) is not int or not 0 <= tick <= run["observed_until_tick"]:
        raise InvalidInputError("replay tick must be an exact observed nonnegative integer")
    try:
        state = _replay_context(context, tick)
        compact = project_snapshot(context.inputs.profile, state)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("coordinator settled replay validation failed") from exc
    return {
        "reader_version": READER_VERSION,
        "scope": "verified_native_settled_state",
        "run_id": identifier,
        "native_run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "tick": tick,
        "last_seq": state.last_seq,
        "observed_until_tick": run["observed_until_tick"],
        "state_boundary": "after_all_observed_events_with_tick_lte_T",
        "reader_capabilities": {
            "arbitrary_settled_state": True,
            "engine_restore": False,
            "geometric_interpolation": False,
            "full_v3": False,
        },
        "snapshot": compact,
    }
