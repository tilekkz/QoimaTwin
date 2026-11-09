"""One physical HU, mandatory resource ownership and append-only observations."""

from types import MappingProxyType

from app.v3.pallet_cycle_types import (
    DRIVER_ID,
    PLATFORM_ID,
    VEHICLE_ID,
    ActiveOperation,
    CycleEvent,
    CycleJob,
    CycleJobView,
    CycleLease,
    ExactPose,
    PalletOwner,
    PhysicalPallet,
)


class CycleInvariantError(RuntimeError):
    """A settled local cycle state violates physical or exclusive ownership."""


class CycleState:
    def __init__(self, hu: PhysicalPallet, jobs: tuple[CycleJob, ...], pose: ExactPose) -> None:
        self.hu = hu
        self.registry = MappingProxyType({hu.hu_id: hu})
        self.jobs = {job.job_id: CycleJobView(job.job_id, "not_arrived") for job in jobs}
        self.owner = PalletOwner(hu.hu_id, "platform", PLATFORM_ID)
        self.pose = pose
        self.leases: dict[str, CycleLease] = {}
        self.active: ActiveOperation | None = None
        self.active_job: str | None = None
        self.operation_index = 0
        self.events: list[CycleEvent] = []
        self.waiting: list[tuple[int, str]] = []
        self.arrivals: dict[str, int] = {}
        self.starts: dict[str, int] = {}
        self.busy: list[tuple[int, int | None]] = []

    def emit(
        self,
        tick: int,
        kind: str,
        job_id: str,
        *,
        operation: ActiveOperation | None = None,
        owner: PalletOwner | None = None,
        lease: CycleLease | None = None,
        job: CycleJobView | None = None,
    ) -> None:
        self.events.append(
            CycleEvent(len(self.events) + 1, tick, kind, job_id, operation, owner, lease, job)
        )

    def job_changed(self, tick: int, view: CycleJobView) -> None:
        self.jobs[view.job_id] = view
        self.emit(tick, "job_changed", view.job_id, job=view)


def resource_ids(hu_id: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                f"worker:{DRIVER_ID}",
                f"vehicle:{VEHICLE_ID}",
                f"slot:{PLATFORM_ID}",
                f"hu:{hu_id}",
                f"action_space:{PLATFORM_ID}:pallet_cycle",
            )
        )
    )


def check_state(state: CycleState, resources: tuple[str, ...], now: int) -> None:
    if len(state.registry) != 1 or state.registry.get(state.hu.hu_id) is not state.hu:
        raise CycleInvariantError("registered physical HU identity or quantity changed")
    if state.owner.hu_id != state.hu.hu_id or state.owner.kind not in ("platform", "vehicle"):
        raise CycleInvariantError("one registered physical HU must have exactly one owner")
    expected_owner = PLATFORM_ID if state.owner.kind == "platform" else VEHICLE_ID
    if state.owner.resource_id != expected_owner:
        raise CycleInvariantError("HU owner resource is incorrect")
    if state.active_job is None:
        if state.active is not None or state.leases or state.owner.kind != "platform":
            raise CycleInvariantError("idle component retains active work, cargo or leases")
        return
    if state.active is None or state.active.job_id != state.active_job:
        raise CycleInvariantError("active cycle has no matching operation")
    if set(state.leases) != set(resources):
        raise CycleInvariantError("active cycle lacks exact exclusive resources")
    if any(
        lease.job_id != state.active_job or lease.resource_id != key
        for key, lease in state.leases.items()
    ):
        raise CycleInvariantError("resources have multiple cycle owners")
    if any(
        type(lease.acquired_tick) is not int or not 0 <= lease.acquired_tick <= now
        for lease in state.leases.values()
    ):
        raise CycleInvariantError("resource lease acquired outside observed time")
    if state.jobs[state.active_job].state != "active":
        raise CycleInvariantError("active job state is inconsistent")
    if state.active.operation.attached != (state.owner.kind == "vehicle"):
        raise CycleInvariantError("physical HU attachment and owner disagree")
    if state.active.planned_end_tick <= state.active.started_tick:
        raise CycleInvariantError("positive operation duration is required")
    if not 0 <= state.active.started_tick <= now < state.active.planned_end_tick:
        raise CycleInvariantError("active operation is outside its observed interval")
    if state.pose != state.active.operation.start_pose:
        raise CycleInvariantError("active operation is not continuous with observed start")
