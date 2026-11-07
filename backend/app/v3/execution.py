"""Bounded, source-bound whole-HU manual DES proposal; not a complete V3 engine."""

from __future__ import annotations

from functools import partial

from app.simulation.scheduler import Phase, PhaseScheduler
from app.v3.execution_invariants import check_manual_invariants
from app.v3.execution_plan import job_plan, next_service_wake, service_window
from app.v3.execution_state import ManualState, Step, Work
from app.v3.execution_types import (
    ActorSpec,
    BoundGraph,
    ExecutionProfile,
    ManualOutcome,
    ManualSnapshot,
    Motion,
    PlaceSpec,
)
from app.v3.execution_validate import fits, validate_profile

WAIT_PRIORITY = ("resources", "port_window", "no_route")


class ManualEngine:
    def __init__(
        self, profile: ExecutionProfile, graph: BoundGraph, *, check_invariants: bool = True
    ) -> None:
        validate_profile(profile, graph)
        self.profile, self.graph = profile, graph
        self.state = ManualState(profile)
        self.scheduler = PhaseScheduler()
        self.scheduler.on_tick_settled = self._settled if check_invariants else None
        self.actors = {a.actor_id: a for a in profile.actors}
        self.ports = {p.port_id: p for p in profile.ports}
        self.units = {h.hu_id: h for h in profile.handling_units}
        self.horizon = 0
        self._ran = False
        self._at_horizon: ManualSnapshot | None = None
        check_manual_invariants(self.state)

    def run(self, horizon_tick: int, end_tick: int) -> ManualOutcome:
        if self._ran:
            raise ValueError("manual engine is one-shot")
        if type(horizon_tick) is not int or type(end_tick) is not int:
            raise ValueError("manual boundaries require integer ticks")
        if horizon_tick <= 0 or end_tick < horizon_tick:
            raise ValueError("manual boundaries require 0 < horizon <= end")
        if any(j.arrival_tick >= horizon_tick for j in self.profile.jobs):
            raise ValueError("job arrivals must lie in [0,horizon)")
        self._ran, self.horizon = True, horizon_tick
        for work in self.state.jobs.values():
            self.scheduler.schedule(
                work.job.arrival_tick,
                Phase.ARRIVAL,
                partial(self._arrive, work),
                key=(work.job.job_id,),
            )
        for tick in sorted({start for p in self.profile.ports for start, _ in p.windows}):
            if tick < horizon_tick:
                self.scheduler.schedule(tick, Phase.ARRIVAL, self._request_dispatch)
        self.scheduler.schedule(horizon_tick, Phase.CHECKPOINT, self._capture_horizon)
        self.scheduler.run(until=end_tick + 1)
        check_manual_invariants(self.state)
        complete = all(w.state == "complete" for w in self.state.jobs.values())
        finish = (self.state.events[-1].tick if self.state.events else 0) if complete else end_tick
        if self._at_horizon is None:
            raise RuntimeError("manual horizon checkpoint was not settled")
        return ManualOutcome(
            self.profile.profile_id,
            tuple(self.state.events),
            self._at_horizon,
            self.state.snapshot(finish),
        )

    def _settled(self, _tick: int, _next_tick: int | None) -> None:
        check_manual_invariants(self.state)

    def _capture_horizon(self) -> None:
        self._at_horizon = self.state.snapshot(self.horizon)

    def _arrive(self, work: Work) -> None:
        now = self.scheduler.now
        self.state.job_changed(now, work, "waiting", "resources")
        self.state.event(now, work, "job_arrived")
        if work.job.direction == "inbound":
            self.state.arrived.add(work.job.hu_id)
            self.state.move_hu(now, work, "outside", "outside")
        self._request_dispatch()

    def _request_dispatch(self) -> None:
        if self.scheduler.running_phase == Phase.DISPATCH:
            return
        self.scheduler.schedule(
            self.scheduler.now, Phase.DISPATCH, self._dispatch, unique="manual_dispatch"
        )

    def _dispatch(self) -> None:
        for work in sorted(
            self.state.jobs.values(), key=lambda w: (w.job.arrival_tick, w.job.job_id)
        ):
            if work.state == "waiting" and self.scheduler.now < self.horizon:
                self._assign(work)
            elif work.state == "active" and not work.running:
                self._continue(work)

    def _available_load(self, work: Work) -> bool:
        owner = self.state.owners[work.job.hu_id]
        if f"hu:{work.job.hu_id}" in self.state.leases:
            return False
        if work.job.direction == "outbound":
            return owner.kind == "stock" and owner.location_id == work.job.slot_id
        return (
            owner.kind == "outside"
            and not any(
                o.kind == "stock" and o.location_id == work.job.slot_id
                for o in self.state.owners.values()
            )
            and f"slot:{work.job.slot_id}" not in self.state.leases
        )

    def _candidates(self, work: Work) -> list[tuple[ActorSpec, PlaceSpec]]:
        port, hu = self.ports[work.job.port_id], self.units[work.job.hu_id]
        skill = "receive" if work.job.direction == "inbound" else "ship"
        actors = sorted(
            (
                a
                for a in self.profile.actors
                if a.actor_id in port.eligible_actor_ids
                and skill in a.skills
                and hu.gross_mass_kg <= a.max_gross_mass_kg
                and f"worker:{a.actor_id}" not in self.state.leases
            ),
            key=lambda a: a.actor_id,
        )
        buffers = sorted(
            (
                b
                for b in port.buffer_places
                if fits(hu, b) and f"buffer:{b.place_id}" not in self.state.leases
            ),
            key=lambda b: b.place_id,
        )
        return [(actor, buffer) for actor in actors for buffer in buffers]

    def _assign(self, work: Work) -> None:
        if not self._available_load(work):
            self.state.job_changed(self.scheduler.now, work, "waiting", "stock_or_slot")
            return
        reasons: set[str] = set()
        for actor, buffer in self._candidates(work):
            steps = job_plan(self.profile, work.job, actor, buffer, self.graph.graph)
            if steps is None:
                reasons.add("no_route")
                continue
            if not self._window(work, steps):
                reasons.add("port_window")
                continue
            if self._acquire_start(work, actor, buffer):
                work.steps = steps
                self._continue(work)
                return
            reasons.add("resources")
        # A candidate blocked only by leases outranks others' window or missing-route failures.
        reason = next((r for r in WAIT_PRIORITY if r in reasons), "resources")
        self.state.job_changed(self.scheduler.now, work, "waiting", reason)

    def _window(self, work: Work, steps: list[Step]) -> bool:
        port, now = self.ports[work.job.port_id], self.scheduler.now
        if service_window(port, now, steps, self.horizon):
            return True
        wake = next_service_wake(port, now, steps, self.horizon)
        if wake is not None:
            self.scheduler.schedule(
                wake,
                Phase.ARRIVAL,
                self._request_dispatch,
                unique=("manual_window", work.job.job_id),
            )
        return False

    def _acquire_start(self, work: Work, actor: ActorSpec, buffer: PlaceSpec) -> bool:
        resources: tuple[str, ...] = (
            f"worker:{actor.actor_id}",
            f"hu:{work.job.hu_id}",
            f"buffer:{buffer.place_id}",
        )
        if work.job.direction == "inbound":
            resources += (f"port:{work.job.port_id}", f"slot:{work.job.slot_id}")
        if not self.state.acquire(self.scheduler.now, work, resources):
            return False
        work.actor_id, work.buffer_id = actor.actor_id, buffer.place_id
        self.state.job_changed(self.scheduler.now, work, "active")
        self.state.worker_changed(self.scheduler.now, work, actor.home_node_id)
        return True

    def _gate(self, work: Work) -> bool:
        port = self.ports[work.job.port_id]
        reason = "port_busy"
        if not self._window(work, work.steps[work.index + 1 :]):
            reason = "port_window"
        elif self.state.acquire(self.scheduler.now, work, (f"port:{port.port_id}",)):
            self.state.job_changed(self.scheduler.now, work, "active")
            return True
        self.state.job_changed(self.scheduler.now, work, "active", reason)
        return False

    def _continue(self, work: Work) -> None:
        while work.index < len(work.steps):
            step = work.steps[work.index]
            if step.effect == "outbound_gate":
                if not self._gate(work):
                    return
                work.index += 1
                continue
            self._begin(work, step)
            if step.ticks:
                work.running = True
                self.scheduler.schedule(
                    self.scheduler.now + step.ticks,
                    Phase.COMPLETION,
                    partial(self._complete_step, work, step),
                    key=(work.job.job_id,),
                )
                return
            self._finish(work, step)
        self._complete_job(work)

    def _begin(self, work: Work, step: Step) -> None:
        if work.actor_id is None:
            raise RuntimeError("job has no assigned actor")
        now = self.scheduler.now
        if step.stage == "intake_service":
            self.state.admitted.add(work.job.hu_id)
            self.state.move_hu(now, work, "service", work.job.port_id)
        if step.stage == "return_home":
            self.state.job_changed(now, work, "returning")
        motion = None
        if step.route is not None:
            if self.state.workers[work.actor_id].node_id != step.route.node_ids[0]:
                raise RuntimeError("manual actor motion would teleport between route anchors")
            motion = Motion(step.route, now, now + step.ticks)
            self.state.worker_changed(now, work, None, motion)
        self.state.event(
            now, work, "operation_started", stage=step.stage, location=step.node_id, motion=motion
        )

    def _complete_step(self, work: Work, step: Step) -> None:
        work.running = False
        self._finish(work, step)
        self._continue(work)
        self._request_dispatch()

    def _finish(self, work: Work, step: Step) -> None:
        now = self.scheduler.now
        if step.route is not None:
            self.state.worker_changed(now, work, step.node_id)
        self.state.event(now, work, "operation_completed", stage=step.stage, location=step.node_id)
        self._effect(work, step.effect)
        work.index += 1

    def _effect(self, work: Work, effect: str) -> None:
        now, job = self.scheduler.now, work.job
        if effect in {"intake_complete", "pickup_stock", "pickup_buffer"}:
            if work.actor_id is None:
                raise RuntimeError("manual pickup has no actor")
            self.state.move_hu(now, work, "worker", work.actor_id)
        if effect == "intake_complete":
            self.state.release(now, work, f"port:{job.port_id}")
        elif effect == "place_buffer":
            if work.buffer_id is None:
                raise RuntimeError("manual putdown has no reserved buffer")
            self.state.move_hu(now, work, "buffer", work.buffer_id)
        elif effect == "pickup_buffer":
            self.state.release(now, work, f"buffer:{work.buffer_id}")
        elif effect == "place_stock":
            self.state.move_hu(now, work, "stock", job.slot_id)
            self.state.release(now, work, f"slot:{job.slot_id}")
            self.state.release(now, work, f"hu:{job.hu_id}")
        elif effect == "ship":
            self.state.move_hu(now, work, "shipped", job.port_id)
            self.state.event(now, work, "hu_shipped", location=job.port_id)
            self.state.release(now, work, f"port:{job.port_id}")
            self.state.release(now, work, f"hu:{job.hu_id}")

    def _complete_job(self, work: Work) -> None:
        if work.actor_id is None:
            raise RuntimeError("completed manual job has no actor")
        now, actor = self.scheduler.now, self.actors[work.actor_id]
        self.state.release(now, work, f"worker:{work.actor_id}")
        self.state.worker_changed(now, work, actor.home_node_id, released=True)
        self.state.job_changed(now, work, "complete")
        self.state.event(now, work, "job_completed")
