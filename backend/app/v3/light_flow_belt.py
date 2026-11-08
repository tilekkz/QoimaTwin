"""Shared-clock adapter; frozen standalone belt engine and elapsed plans stay unchanged."""

import heapq
from dataclasses import replace
from typing import Protocol

from app.v3.belt_engine import BeltEngine
from app.v3.belt_geometry import footprint, requirements
from app.v3.belt_models import BeltEvent, BeltJob, BeltStep
from app.v3.belt_plan import compile_job
from app.v3.belt_state import RunningCarrier
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource


class BeltHooks(Protocol):
    def station_ready(self, state: RunningCarrier, stage: str) -> bool: ...
    def station_started(self, state: RunningCarrier, stage: str) -> None: ...
    def station_finished(self, state: RunningCarrier, stage: str) -> None: ...
    def output_ready(self, state: RunningCarrier) -> None: ...
    def belt_event(self, event: BeltEvent) -> None: ...


class FlowBelt(BeltEngine):
    def __init__(self, source: ConveyorSource, hooks: BeltHooks, clear_tick: int) -> None:
        super().__init__(source, ())
        self.hooks, self.clear_tick = hooks, clear_tick
        self.external: dict[str, str] = {}
        self.at_output: set[str] = set()
        self.stage_indices: dict[str, tuple[int, int]] = {}

    def prepared_steps(self, job: BeltJob) -> tuple[BeltStep, ...]:
        steps = compile_job(self.source, job)
        index = next(i for i, step in enumerate(steps) if step.phase == "station")
        self.stage_indices[job.job_id] = index, index + 1
        return (
            *steps[: index + 1],
            replace(steps[index], duration_tick=self.clear_tick),
            *steps[index + 1 :],
        )

    def reserve(self, order_id: str, resources: frozenset[str]) -> bool:
        if any(
            self.leases.get(r, order_id) != order_id or self.external.get(r, order_id) != order_id
            for r in resources
        ):
            return False
        self.external.update((resource, order_id) for resource in resources)
        return True

    def reserve_intake(self, job: BeltJob) -> bool:
        return self.reserve(job.job_id, self.prepared_steps(job)[0].resources)

    def admit(self, job: BeltJob, tick: int) -> None:
        self.tick = tick
        state = RunningCarrier(job, self.prepared_steps(job), arrived=True, waiting_since=tick)
        if any(s.job.job_id == job.job_id for s in self.states):
            raise RuntimeError("Duplicate physical belt job")
        self.states += (state,)
        self._remove_external(job.job_id)
        self._emit(state, "arrived")
        self._start(state)
        if not state.admitted:
            raise RuntimeError("Reserved intake handoff lost physical capacity")

    def reserve_replacement(self, state: RunningCarrier, payload: ConveyorPayload) -> bool:
        self._replacement_steps(state, payload)  # validates the whole remaining directed route
        assert state.pose is not None
        cells = footprint(self.source, payload, state.pose)
        return self.reserve(state.job.job_id, requirements(self.source, cells))

    def replace_payload(self, state: RunningCarrier, payload: ConveyorPayload) -> None:
        steps = self._replacement_steps(state, payload)
        for resource, owner in tuple(self.external.items()):
            if owner == state.job.job_id:
                self.leases[resource] = owner
        self._remove_external(state.job.job_id)
        state.job = replace(state.job, hu_id=payload.payload_id, payload=payload)
        state.steps = (*state.steps[: state.index + 1], *steps)
        self._emit(state, "container_replaced")

    def _replacement_steps(
        self, state: RunningCarrier, payload: ConveyorPayload
    ) -> tuple[BeltStep, ...]:
        candidate = replace(state.job, hu_id=payload.payload_id, payload=payload)
        steps = compile_job(self.source, candidate)
        index = next(i for i, step in enumerate(steps) if step.phase == "station")
        if steps[index].end != state.pose:
            raise RuntimeError("Replacement may not reset physical pose")
        return steps[index + 1 :]

    def finish_due(self, tick: int) -> None:
        self.tick = tick
        while self.pending and self.pending[0][0] == tick:
            _, phase, index = heapq.heappop(self.pending)
            if phase != 0:
                raise RuntimeError("External arrivals must use real intake handoff")
            self._finish(self.states[index])

    def dispatch(self, tick: int) -> None:
        self.tick = tick
        waiting = sorted(
            (s for s in self.states if not s.complete and s.active is None),
            key=lambda s: (s.waiting_since or 0, s.job.job_id),
        )
        for state in waiting:
            self._start(state)

    def collect(self, order_id: str) -> None:
        state = next(s for s in self.states if s.job.job_id == order_id)
        if order_id not in self.at_output:
            raise RuntimeError("Package has not physically reached output")
        state.stop_waiting(self.tick)
        state.complete, state.index = True, len(state.steps)
        self.at_output.remove(order_id)
        self._release(state, frozenset())
        self._emit(state, "completed")

    def _start(self, state: RunningCarrier) -> None:
        if state.job.job_id in self.at_output:
            return
        step = state.steps[state.index]
        if any(self.external.get(r, state.job.job_id) != state.job.job_id for r in step.resources):
            return
        if step.phase == "station":
            stage = "pack" if state.index == self.stage_indices[state.job.job_id][0] else "clear"
            if not self.hooks.station_ready(state, stage):
                return
            super()._start(state)
            if state.active is not None:
                self.hooks.station_started(state, stage)
        else:
            super()._start(state)

    def _finish(self, state: RunningCarrier) -> None:
        assert state.active is not None
        if state.steps[state.index].phase == "station":
            stage = "pack" if state.index == self.stage_indices[state.job.job_id][0] else "clear"
            self.hooks.station_finished(state, stage)
        if state.index == len(state.steps) - 1:
            state.pose, state.active = state.active.end, None
            state.waiting_since = self.tick
            self._emit(state, "motion_completed")
            self.at_output.add(state.job.job_id)
            self.hooks.output_ready(state)
        else:
            super()._finish(state)

    def _emit(
        self, state: RunningCarrier, kind: str, resources: tuple[str, ...] | None = None
    ) -> None:
        super()._emit(state, kind, resources)
        self.hooks.belt_event(self.events[-1])

    def _remove_external(self, order_id: str) -> None:
        self.external = {r: owner for r, owner in self.external.items() if owner != order_id}
