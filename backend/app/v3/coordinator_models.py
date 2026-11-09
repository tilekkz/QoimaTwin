"""Versioned B1 shared-clock staffing values; helper packing is a later stage."""

from dataclasses import dataclass

from app.v3.coordinator_packing_models import PackingView, UnitContext
from app.v3.coordinator_units_models import UnitResources
from app.v3.coordinator_units_state import UnitProgress
from app.v3.light_flow_models import FlowCartView
from app.v3.staff_registry import StaffRegistry
from app.v3.staff_registry_values import Role
from app.v3.whole_flow_models import (
    WholeFlowEvent,
    WholeFlowOutcome,
    WholeFlowProfile,
    WholeFlowSnapshot,
)

COORDINATOR_VERSION = "qoima-staff-coordinator-v3-proposal-3"


@dataclass(frozen=True, slots=True)
class RoleStation:
    station_id: str
    node_id: str
    bench_owner: str


@dataclass(frozen=True, slots=True)
class RoleIntent:
    intent_id: str
    actor_id: str
    station_id: str
    request_tick: int
    return_tick: int
    restore_by_tick: int
    restore_node: str


@dataclass(frozen=True, slots=True)
class CoordinatorProfile:
    profile_id: str
    provenance: str
    world: WholeFlowProfile
    registry: StaffRegistry
    stations: tuple[RoleStation, ...]
    intents: tuple[RoleIntent, ...]
    unit_resources: UnitResources | None = None


@dataclass(frozen=True, slots=True)
class RoleView:
    intent_id: str
    actor_id: str
    station_id: str
    status: str
    departed_tick: int | None
    activated_tick: int | None
    return_started_tick: int | None
    restored_tick: int | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class ActorRoleView:
    actor_id: str
    primary_role: Role
    effective_role: str
    available: bool
    intent_id: str | None


@dataclass(frozen=True, slots=True)
class RoleExposure:
    role_ticks: tuple[tuple[str, int], ...]
    transition_ticks: int
    unavailable_ticks: int


@dataclass(frozen=True, slots=True)
class StaffViolation:
    tick: int
    actor_id: str
    reason: str
    intent_id: str | None = None


@dataclass(frozen=True, slots=True)
class CoordinatorEvent(WholeFlowEvent):
    work_kind: str = "role_intent"
    role_view: RoleView | None = None
    unit_context: UnitContext | None = None
    packing: PackingView | None = None
    packing_wait_reason: str | None = None
    resource_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CoordinatorSnapshot(WholeFlowSnapshot):
    roles: tuple[RoleView, ...]
    actor_roles: tuple[ActorRoleView, ...]
    role_bindings: tuple[tuple[str, str], ...]
    exposure: RoleExposure
    unit_contexts: tuple[UnitContext, ...] = ()
    packing: tuple[PackingView, ...] = ()
    packing_waits: tuple[tuple[str, str], ...] = ()
    carts: tuple[FlowCartView, ...] = ()
    cart_releases: tuple[tuple[str, int], ...] = ()
    unit_progress: tuple[UnitProgress, ...] = ()


@dataclass(frozen=True, slots=True)
class CoordinatorOutcome(WholeFlowOutcome):
    at_horizon: CoordinatorSnapshot
    at_end: CoordinatorSnapshot
    checkpoints: tuple[CoordinatorSnapshot, ...] = ()
    business_complete_tick: int | None = None
    resource_drained_tick: int | None = None
    observation_end_tick: int = 0
    staffing_status: str = "partial"
    constraint_violations: tuple[StaffViolation, ...] = ()
