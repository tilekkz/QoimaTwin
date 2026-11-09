"""Bounded finite conveyor DES over explicit source-bound routes and carrier recipes."""

import heapq

from app.v3.belt_geometry import footprint, requirements
from app.v3.belt_models import BeltEvent, BeltJob, BeltMotion, BeltOutcome, BeltSnapshot
from app.v3.belt_plan import compile_job, valid_tick
from app.v3.belt_state import RunningCarrier, settled_invariants, snapshot
from app.v3.conveyor_models import ConveyorSource


class BeltEngine:
    def __init__(
        self, source: ConveyorSource, jobs: tuple[BeltJob, ...], *, check_invariants: bool = True
    ) -> None:
        for values in (
            {job.job_id for job in jobs},
            {job.hu_id for job in jobs},
            {job.payload.payload_id for job in jobs},
        ):
            if len(values) != len(jobs):
                raise ValueError("Duplicate job, HU or carrier identity")
        self.source = source
        self.states = tuple(
            RunningCarrier(job, compile_job(source, job))
            for job in sorted(jobs, key=lambda job: job.job_id)
        )
        self.check_invariants = check_invariants
        self.leases: dict[str, str] = {}
        self.events: list[BeltEvent] = []
        self.pending: list[tuple[int, int, int]] = []
        self.tick = 0
        self.used = False

    def run(self, horizon_tick: int, end_tick: int) -> BeltOutcome:
        if self.used or not valid_tick(horizon_tick) or not valid_tick(end_tick):
            raise ValueError("Engine is single-use and clocks must be nonnegative integers")
        if horizon_tick == 0 or end_tick < horizon_tick:
            raise ValueError("Require0 < horizon <= end cap")
        if any(state.job.arrival_tick >= horizon_tick for state in self.states):
            raise ValueError("Materialized arrivals must precede horizon")
        self.used = True
        self.pending = [(s.job.arrival_tick, 1, i) for i, s in enumerate(self.states)]
        heapq.heapify(self.pending)
        at_horizon: BeltSnapshot | None = None
        while self.pending and self.pending[0][0] <= end_tick:
            next_tick = self.pending[0][0]
            if at_horizon is None and horizon_tick < next_tick:
                at_horizon = self._observe(horizon_tick)
            self.tick = next_tick
            self._settle_tick()
            if self.tick == horizon_tick:
                at_horizon = self._observe(horizon_tick)
            if all(state.complete for state in self.states):
                break
        complete = all(state.complete for state in self.states)
        at_end = self._observe(self.tick if complete else end_tick)
        return BeltOutcome(
            "complete" if complete else "partial",
            tuple(self.events),
            at_horizon or self._observe(horizon_tick),
            at_end,
        )

    def _observe(self, tick: int) -> BeltSnapshot:
        if self.check_invariants:
            settled_invariants(self.source, self.states, self.leases, tick)
        return snapshot(self.source, self.states, self.leases, tick)

    def _settle_tick(self) -> None:
        while self.pending and self.pending[0][0] == self.tick:
            _, phase, index = heapq.heappop(self.pending)
            state = self.states[index]
            if phase == 0:
                self._finish(state)
            else:
                state.arrived, state.waiting_since = True, self.tick
                self._emit(state, "arrived")
        waiting = sorted(
            (s for s in self.states if s.arrived and not s.complete and s.active is None),
            key=lambda s: (
                s.waiting_since if s.waiting_since is not None else self.tick,
                s.job.job_id,
            ),
        )
        for state in waiting:
            self._start(state)
        if self.check_invariants:
            settled_invariants(self.source, self.states, self.leases, self.tick)

    def _start(self, state: RunningCarrier) -> None:
        step = state.steps[state.index]
        if any(
            self.leases.get(resource, state.job.job_id) != state.job.job_id
            for resource in step.resources
        ):
            return
        acquired = step.resources - self.leases.keys()
        self.leases.update((resource, state.job.job_id) for resource in acquired)
        state.pose = step.start
        if acquired:
            self._emit(state, "leases_acquired", tuple(sorted(acquired)))
        if not state.admitted:
            state.admitted = True
            self._emit(state, "admitted")
        state.stop_waiting(self.tick)
        state.active = BeltMotion(
            step.phase, self.tick, self.tick + step.duration_tick, step.start, step.end
        )
        heapq.heappush(self.pending, (state.active.planned_end_tick, 0, self.states.index(state)))
        self._emit(state, step.phase + "_started")

    def _finish(self, state: RunningCarrier) -> None:
        motion = state.active
        if motion is None or motion.planned_end_tick != self.tick:
            raise RuntimeError("Mismatched completion")
        state.pose, state.active = motion.end, None
        self._emit(state, motion.phase + "_completed")
        state.index += 1
        if state.index == len(state.steps):
            state.complete = True
            self._release(state, frozenset())
            self._emit(state, "completed")
            return
        current = requirements(self.source, footprint(self.source, state.job.payload, motion.end))
        self._release(state, current | state.steps[state.index].guards)
        state.waiting_since = self.tick

    def _release(self, state: RunningCarrier, keep: frozenset[str]) -> None:
        released = tuple(
            sorted(
                key
                for key, owner in self.leases.items()
                if owner == state.job.job_id and key not in keep
            )
        )
        for key in released:
            del self.leases[key]
        if released:
            self._emit(state, "leases_released", released)

    def _emit(
        self, state: RunningCarrier, kind: str, resources: tuple[str, ...] | None = None
    ) -> None:
        held = tuple(sorted(key for key, owner in self.leases.items() if owner == state.job.job_id))
        self.events.append(
            BeltEvent(
                len(self.events),
                self.tick,
                kind,
                state.job.job_id,
                state.job.hu_id,
                state.job.payload.payload_id,
                state.pose.edge_id if state.pose else None,
                state.pose,
                state.active.planned_end_tick if state.active else None,
                held if resources is None else resources,
            )
        )
