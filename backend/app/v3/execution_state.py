"""Mutable manual DES state and immutable observations."""

from collections import Counter
from dataclasses import dataclass, field

from app.v3.execution_types import (
    ExecutionProfile,
    HUOwner,
    JobView,
    Lease,
    ManualEvent,
    ManualSnapshot,
    Motion,
    TimedJob,
    WorkerView,
)
from app.v3.runtime_graph import CandidateRoute


@dataclass(frozen=True, slots=True)
class Step:
    stage: str
    ticks: int
    node_id: str
    effect: str = ""
    route: CandidateRoute | None = None


@dataclass(slots=True)
class Work:
    job: TimedJob
    state: str = "unreleased"
    wait_reason: str | None = "not_arrived"
    actor_id: str | None = None
    buffer_id: str | None = None
    steps: list[Step] = field(default_factory=list)
    index: int = 0
    running: bool = False


class ManualState:
    def __init__(self, profile: ExecutionProfile) -> None:
        self.profile = profile
        self.jobs = {j.job_id: Work(j) for j in profile.jobs}
        self.workers = {
            a.actor_id: WorkerView(a.actor_id, a.home_node_id, None, None) for a in profile.actors
        }
        self.owners = {
            h.hu_id: HUOwner(h.hu_id, "unreleased", "outside") for h in profile.handling_units
        }
        for item in profile.initial_placements:
            self.owners[item.hu_id] = HUOwner(item.hu_id, "stock", item.slot_id)
        self.leases: dict[str, Lease] = {}
        self.events: list[ManualEvent] = []
        self.arrived: set[str] = set()
        self.admitted: set[str] = set()

    def event(
        self,
        tick: int,
        work: Work,
        kind: str,
        *,
        stage: str | None = None,
        location: str | None = None,
        resources: tuple[str, ...] = (),
        motion: Motion | None = None,
        owner: HUOwner | None = None,
        job: JobView | None = None,
        worker: WorkerView | None = None,
    ) -> None:
        self.events.append(
            ManualEvent(
                len(self.events),
                tick,
                kind,
                work.job.job_id,
                work.job.hu_id,
                work.actor_id,
                stage,
                location,
                resources,
                motion,
                owner,
                job,
                worker,
            )
        )

    def job_changed(self, tick: int, work: Work, state: str, reason: str | None = None) -> None:
        old = JobView(work.job.job_id, work.state, work.wait_reason, work.actor_id)
        work.state, work.wait_reason = state, reason
        current = JobView(work.job.job_id, work.state, work.wait_reason, work.actor_id)
        if old != current:
            self.event(tick, work, "job_changed", job=current)

    def worker_changed(
        self,
        tick: int,
        work: Work,
        node: str | None,
        motion: Motion | None = None,
        *,
        released: bool = False,
    ) -> None:
        if work.actor_id is None:
            raise RuntimeError("manual operation requires an actual actor")
        worker = WorkerView(work.actor_id, node, motion, None if released else work.job.job_id)
        self.workers[work.actor_id] = worker
        self.event(tick, work, "worker_changed", worker=worker)

    def move_hu(self, tick: int, work: Work, kind: str, location: str) -> None:
        owner = HUOwner(work.job.hu_id, kind, location)
        self.owners[owner.hu_id] = owner
        self.event(tick, work, "hu_owner_changed", owner=owner)

    def acquire(self, tick: int, work: Work, resources: tuple[str, ...]) -> bool:
        if any(resource in self.leases for resource in resources):
            return False
        for resource in sorted(resources):
            self.leases[resource] = Lease(resource, work.job.job_id, tick)
            self.event(tick, work, "lease_acquired", resources=(resource,))
        return True

    def release(self, tick: int, work: Work, resource: str) -> None:
        lease = self.leases.get(resource)
        if lease is None or lease.job_id != work.job.job_id:
            raise RuntimeError("attempted release of another job's resource")
        del self.leases[resource]
        self.event(tick, work, "lease_released", resources=(resource,))

    def units(self, kinds: set[str]) -> tuple[tuple[str, int], ...]:
        result: Counter[str] = Counter()
        for hu in self.profile.handling_units:
            if self.owners[hu.hu_id].kind in kinds:
                result[hu.sku_id] += hu.quantity
        return tuple(sorted(result.items()))

    def snapshot(self, tick: int) -> ManualSnapshot:
        jobs = tuple(
            JobView(w.job.job_id, w.state, w.wait_reason, w.actor_id)
            for w in sorted(self.jobs.values(), key=lambda w: w.job.job_id)
        )
        return ManualSnapshot(
            tick,
            "complete" if all(j.state == "complete" for j in jobs) else "partial",
            jobs,
            tuple(self.workers[k] for k in sorted(self.workers)),
            tuple(self.owners[k] for k in sorted(self.owners)),
            tuple(self.leases[k] for k in sorted(self.leases)),
            self.units({"stock"}),
            self.units({"worker", "buffer", "service"}),
            self.units({"outside"}),
            self.units({"shipped"}),
        )
