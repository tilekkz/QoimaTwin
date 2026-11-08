"""Timed fixed-geometry local cycle with one HU and mandatory exclusive leases."""

from dataclasses import replace
from fractions import Fraction
from functools import partial
from heapq import heappop, heappush
from pathlib import Path

from app.simulation.scheduler import Phase, PhaseScheduler
from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_bridge import build_bridges
from app.v3.pallet_cycle_observe import snapshot
from app.v3.pallet_cycle_plan import build_cycle_plan, validate_timing
from app.v3.pallet_cycle_proof import validate_proof
from app.v3.pallet_cycle_state import CycleState, check_state, resource_ids
from app.v3.pallet_cycle_types import (
    PLATFORM_ID,
    VEHICLE_ID,
    ActiveOperation,
    CycleBridge,
    CycleJob,
    CycleJobView,
    CycleLease,
    CycleOutcome,
    CycleTimingProfile,
    PalletOwner,
    PhysicalPallet,
)


def _validate_jobs(jobs: tuple[CycleJob, ...], hu: PhysicalPallet, mesh_hash: str) -> None:
    if (
        not isinstance(hu.hu_id, str)
        or not hu.hu_id.strip()
        or hu.cargo_class != "PALLET_LOAD"
        or type(hu.units) is not int
        or hu.units != 24
        or type(hu.gross_mass_kg) is not Fraction
        or hu.gross_mass_kg != 455
        or hu.model_sha256 != mesh_hash
    ):
        raise ValueError("only the declared physical PALLET fixture is supported")
    ids: set[str] = set()
    for job in jobs:
        if not isinstance(job.job_id, str) or not job.job_id.strip() or job.job_id in ids:
            raise ValueError("cycle job IDs must be unique nonempty strings")
        if type(job.ready_tick) is not int or job.ready_tick < 0 or job.hu_id != hu.hu_id:
            raise ValueError("job has invalid ready tick or unknown physical HU")
        ids.add(job.job_id)


class PalletCycleEngine:
    def __init__(
        self,
        profile: CycleTimingProfile,
        jobs: tuple[CycleJob, ...],
        hu: PhysicalPallet,
        proof_root: Path,
        proof: LocalGeometryProof,
        *,
        source_approach: bool = False,
        base_source_root: Path | None = None,
        vehicle_source_root: Path | None = None,
    ) -> None:
        validate_timing(profile)
        if type(proof) is not LocalGeometryProof:
            raise ValueError("an independently verified local geometry proof is required")
        _validate_jobs(jobs, hu, proof.mesh_sha256)
        if type(source_approach) is not bool:
            raise ValueError("source_approach must be an explicit boolean")
        self.profile = profile
        self.proof = validate_proof(proof_root, proof)
        self.jobs = tuple(sorted(jobs, key=lambda item: (item.ready_tick, item.job_id)))
        self.plan = build_cycle_plan(proof_root, profile)
        self.bridge: CycleBridge | None = None
        if source_approach:
            entry, exit_op, self.bridge = build_bridges(
                proof_root,
                profile,
                self.plan[0].start_pose,
                base_source_root or proof_root.parent / "v3-proposal",
                vehicle_source_root or proof_root.parent / "v3-vehicle-proposal",
            )
            self.plan = tuple(
                replace(op, ordinal=i) for i, op in enumerate((entry, *self.plan, exit_op))
            )
        self.state = CycleState(hu, self.jobs, self.plan[0].start_pose)
        self.resources = resource_ids(hu.hu_id)
        if self.bridge is not None:
            self.resources = tuple(sorted(set(self.resources) | set(self.bridge.resource_ids)))
        self.scheduler = PhaseScheduler()
        self.scheduler.on_tick_settled = lambda _tick, _next: self.check_invariants()
        self.horizon = 0
        self._ran = False

    def check_invariants(self) -> None:
        check_state(self.state, self.resources, self.scheduler.now)

    def run(self, horizon_tick: int, end_tick_limit: int) -> CycleOutcome:
        if self._ran:
            raise ValueError("a cycle engine instance runs once")
        if (
            type(horizon_tick) is not int
            or type(end_tick_limit) is not int
            or not (0 <= horizon_tick <= end_tick_limit)
        ):
            raise ValueError("integer horizon and end limit must satisfy 0 <= H <= end")
        self._ran, self.horizon = True, horizon_tick
        self.check_invariants()
        for job in self.jobs:
            if job.ready_tick <= horizon_tick:
                self.scheduler.schedule(
                    job.ready_tick,
                    Phase.ARRIVAL,
                    partial(self._arrive, job),
                    key=(job.job_id,),
                )
        self.scheduler.run(horizon_tick + 1)
        at_horizon = snapshot(self.state, horizon_tick)
        self.scheduler.run(end_tick_limit + 1)
        end = end_tick_limit if self.scheduler.peek_next_tick() is not None else self.scheduler.now
        return CycleOutcome(
            self.profile.profile_id,
            tuple(self.state.events),
            at_horizon,
            snapshot(self.state, end),
            self.proof.bindings,
            self.bridge is not None,
            self.proof,
            tuple(self.state.registry.values()),
            end_tick_limit,
            self.bridge,
        )

    def _request_dispatch(self) -> None:
        now = self.scheduler.now
        self.scheduler.schedule(now, Phase.DISPATCH, self._dispatch, unique=("cycle_dispatch", now))

    def _arrive(self, job: CycleJob) -> None:
        self.state.arrivals[job.job_id] = job.ready_tick
        heappush(self.state.waiting, (job.ready_tick, job.job_id))
        self.state.job_changed(self.scheduler.now, CycleJobView(job.job_id, "waiting", "resources"))
        self._request_dispatch()

    def _dispatch(self) -> None:
        now, state = self.scheduler.now, self.state
        if state.active_job is not None or not state.waiting:
            return
        if now > self.horizon:
            for _, job_id in sorted(state.waiting):
                state.job_changed(now, CycleJobView(job_id, "waiting", "horizon_closed"))
            return
        if state.leases:
            raise RuntimeError("idle cycle unexpectedly holds shared resources")
        _, job_id = heappop(state.waiting)
        state.active_job, state.operation_index = job_id, 0
        state.starts[job_id] = now
        state.busy.append((now, None))
        state.leases = {key: CycleLease(key, job_id, now) for key in self.resources}
        for lease in state.leases.values():
            state.emit(now, "lease_acquired", job_id, lease=lease)
        state.job_changed(now, CycleJobView(job_id, "active"))
        state.emit(now, "cycle_started", job_id)
        self._start_operation()

    def _start_operation(self) -> None:
        now, state = self.scheduler.now, self.state
        job_id = state.active_job
        if job_id is None:
            raise RuntimeError("cannot start an unowned operation")
        operation = self.plan[state.operation_index]
        if state.pose != operation.start_pose:
            raise RuntimeError("operation would teleport the vehicle or carriage")
        active = ActiveOperation(job_id, operation, now, now + operation.duration_ticks)
        state.active = active
        state.emit(now, "operation_started", job_id, operation=active)
        self.scheduler.schedule(
            active.planned_end_tick,
            Phase.COMPLETION,
            self._complete_operation,
            key=(job_id, operation.ordinal),
        )

    def _complete_operation(self) -> None:
        now, state = self.scheduler.now, self.state
        active = state.active
        if active is None or now != active.planned_end_tick:
            raise RuntimeError("completion has no matching observed operation")
        state.pose = active.operation.end_pose
        state.emit(now, "operation_completed", active.job_id, operation=active)
        kind = active.operation.kind
        if kind in ("attach", "release"):
            state.owner = PalletOwner(
                state.hu.hu_id,
                "vehicle" if kind == "attach" else "platform",
                VEHICLE_ID if kind == "attach" else PLATFORM_ID,
            )
            state.emit(now, "owner_changed", active.job_id, owner=state.owner)
        state.active = None
        state.operation_index += 1
        if state.operation_index == len(self.plan):
            self._finish_cycle(active.job_id)
        else:
            self.scheduler.schedule(
                now,
                Phase.DISPATCH,
                self._start_operation,
                key=(active.job_id, state.operation_index),
            )

    def _finish_cycle(self, job_id: str) -> None:
        now, state = self.scheduler.now, self.state
        state.job_changed(now, CycleJobView(job_id, "complete"))
        for resource in self.resources:
            state.emit(now, "lease_released", job_id, lease=state.leases.pop(resource))
        started, _ = state.busy[-1]
        state.busy[-1] = started, now
        state.active_job = None
        state.emit(now, "cycle_completed", job_id)
        self._request_dispatch()
