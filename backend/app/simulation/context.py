"""Compiled run inputs and the shared context that subsystems use."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import pairwise
from typing import Any

from app.contracts.actors import ActorRegistry
from app.contracts.assignment import Assignment
from app.contracts.base import exact
from app.contracts.config import SimulationConfig
from app.contracts.layout import Graph, Layout
from app.contracts.scenario import Scenario
from app.conveyor.topology import ConveyorTopology
from app.inventory.ledger import Holding, Ledger, Location, LocKind
from app.navigation.shortest_paths import AllPairsPaths
from app.simulation.clock import TimeGrid
from app.simulation.recorder import Recorder, Vec3, Waypoint
from app.simulation.scheduler import Phase, PhaseScheduler
from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex


class InputError(ValueError):
    """Run inputs are inconsistent with each other (reported as HTTP 422 by the API)."""


FORECAST_RUNTIME_KEYS = frozenset(
    {"semantic_id", "cpu_time_s", "validation_cpu_time_s", "final_fit_cpu_time_s"}
)
PLAN_SELF_ID = "plan_id"


@dataclass(frozen=True, slots=True)
class SemanticJson:
    """Immutable canonical copy of a semantic JSON object (ADR 0008, 0016).

    `canonical` is fixed at the boundary, so later mutation of the caller's dict cannot change
    identity. `sha256` hashes the content without its self-declared ID field; a declared ID is
    never trusted, only checked against that hash. `to_dict()` returns a fresh copy.
    """

    canonical: bytes
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = parse_json(self.canonical)
        return data


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return _plain_object(value)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _plain_object(value: Mapping[Any, object]) -> dict[Any, object]:
    """Deep copy into plain dicts/lists, so the caller keeps no reference into the inputs."""
    return {key: _plain(item) for key, item in value.items()}


def semantic_json(
    value: object, *, name: str, self_id: str | None = None, forbidden: frozenset[str] = frozenset()
) -> SemanticJson:
    """Validate, copy and hash a JSON object; reject runtime fields and false self-IDs."""
    if isinstance(value, SemanticJson):
        rebuilt = semantic_json(value.to_dict(), name=name, self_id=self_id, forbidden=forbidden)
        if rebuilt != value:
            raise InputError(f"{name}: SemanticJson does not match its content")
        return value
    if not isinstance(value, Mapping):
        raise InputError(f"{name} must be a JSON object")
    data = _plain_object(value)
    rejected = sorted(forbidden & set(data))
    if rejected:
        raise InputError(f"{name} must hold semantics only; remove {rejected}")
    try:
        canonical = canonical_bytes(data)
        content = {key: item for key, item in data.items() if key != self_id}
        digest = sha256_hex(content)
    except (TypeError, ValueError) as exc:
        raise InputError(f"{name} is not canonical JSON: {exc}") from exc
    if self_id is not None and self_id in data and data[self_id] != digest:
        raise InputError(f"{name}: declared {self_id} does not match its content hash")
    return SemanticJson(canonical, digest)


@dataclass(frozen=True, slots=True)
class RunInputs:
    """Run inputs. Optional semantics are frozen at construction (see SemanticJson).

    `forecast_snapshot` takes ForecastSnapshot.semantic_dict() (no CPU timings, no declared ID);
    `relocation_plan` takes PlanArtifact.model_dump(mode="json"); its plan_id must match.
    """

    layout: Layout
    config: SimulationConfig
    actors: ActorRegistry
    assignment: Assignment
    scenario: Scenario
    experiment_type: str = "slotting"
    forecast_snapshot: SemanticJson | Mapping[str, Any] | None = field(default=None, kw_only=True)
    relocation_plan: SemanticJson | Mapping[str, Any] | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.forecast_snapshot is not None:
            frozen = semantic_json(
                self.forecast_snapshot, name="forecast_snapshot", forbidden=FORECAST_RUNTIME_KEYS
            )
            object.__setattr__(self, "forecast_snapshot", frozen)
        if self.relocation_plan is not None:
            frozen = semantic_json(
                self.relocation_plan, name="relocation_plan", self_id=PLAN_SELF_ID
            )
            object.__setattr__(self, "relocation_plan", frozen)

    def forecast_json(self) -> SemanticJson | None:
        """The frozen forecast semantics (always a SemanticJson after construction)."""
        return _frozen(self.forecast_snapshot)

    def relocation_json(self) -> SemanticJson | None:
        """The frozen relocation plan semantics (always a SemanticJson after construction)."""
        return _frozen(self.relocation_plan)


def _frozen(value: SemanticJson | Mapping[str, Any] | None) -> SemanticJson | None:
    if value is not None and not isinstance(value, SemanticJson):
        raise InputError("semantic input was not frozen at construction")
    return value


@dataclass(frozen=True, slots=True)
class GraphGeometry:
    paths: AllPairsPaths
    positions: dict[str, Vec3]

    @classmethod
    def of(cls, graph: Graph) -> GraphGeometry:
        return cls(AllPairsPaths.from_graph(graph), {n.node_id: n.pos for n in graph.nodes})

    def waypoints(
        self, source: str, target: str, start: int, ticks_per_metre: Fraction
    ) -> tuple[tuple[Waypoint, ...], int]:
        """Waypoints along the canonical path and the arrival tick (exact integer ticks)."""
        nodes = self.paths.path(source, target)
        points = [Waypoint(nodes[0], self.positions[nodes[0]], start)]
        travelled = Fraction(0)
        for prev, node in pairwise(nodes):
            travelled += self.paths.require_distance(prev, node)
            at = start + _exact_ticks(travelled * ticks_per_metre)
            points.append(Waypoint(node, self.positions[node], at))
        return tuple(points), points[-1].at_tick


def _exact_ticks(value: Fraction) -> int:
    if value.denominator != 1:
        raise InputError(f"travel time {value} ticks is not on the time grid")
    return value.numerator


@dataclass(slots=True)
class SimContext:
    inputs: RunInputs
    grid: TimeGrid
    sched: PhaseScheduler
    recorder: Recorder
    ledger: Ledger
    topology: ConveyorTopology
    walk: GraphGeometry
    outbound: GraphGeometry
    inbound: GraphGeometry
    sku_holding: dict[str, Holding]
    slot_node: dict[str, str]
    dispatch_handler: Callable[[], None] | None = None
    dispatch_dirty: bool = False
    counters: dict[str, int] = field(default_factory=dict)

    @property
    def now(self) -> int:
        return self.sched.now

    @property
    def config(self) -> SimulationConfig:
        return self.inputs.config

    def ticks(self, seconds: float | Fraction) -> int:
        value = seconds if isinstance(seconds, Fraction) else exact(seconds)
        return self.grid.ticks(value)

    def walk_ticks_per_metre(self) -> Fraction:
        return self.grid.ticks_per_second / exact(self.config.walk_speed_mps)

    def drive_ticks_per_metre(self) -> Fraction:
        return self.grid.ticks_per_second / exact(self.config.forklift_speed_mps)

    def next_id(self, prefix: str, width: int = 5) -> str:
        value = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = value
        return f"{prefix}{value:0{width}d}"

    def request_dispatch(self) -> None:
        """Ask for a phase-3 dispatch cycle at the current tick (coalesced)."""
        running = self.sched.running_phase
        if running is Phase.DISPATCH:
            self.dispatch_dirty = True
            return
        tick = self.now if running is None or running < Phase.DISPATCH else self.now + 1
        self.sched.schedule(tick, Phase.DISPATCH, self._run_dispatch, unique="dispatch")

    def _run_dispatch(self) -> None:
        if self.dispatch_handler is None:
            raise RuntimeError("no dispatch handler is installed")
        self.dispatch_handler()


def build_ledger(inputs: RunInputs) -> tuple[Ledger, dict[str, Holding]]:
    """Initial stock from the assignment; returns the ledger and SKU -> active pick-face holding."""
    slots = {s.slot_id: s for s in inputs.layout.slots}
    ledger = Ledger()
    active: dict[str, Holding] = {}
    for lot in inputs.assignment.initial_lots:
        slot = slots.get(lot.slot_id)
        if slot is None:
            raise InputError(f"lot {lot.lot_id} is on unknown slot {lot.slot_id}")
        kind = LocKind.PICKFACE if slot.kind == "pickface" else LocKind.RESERVE_SLOT
        location = Location(kind, lot.slot_id)
        ledger.add_initial(lot.sku_id, lot.lot_id, location, lot.quantity)
        if kind is LocKind.PICKFACE:
            if inputs.assignment.active_assignment.get(lot.slot_id) != lot.sku_id:
                raise InputError(f"lot {lot.lot_id} disagrees with the active assignment")
            if lot.sku_id in active:
                raise InputError(f"SKU {lot.sku_id} has two active pick-face lots")
            active[lot.sku_id] = Holding(lot.sku_id, lot.lot_id, location)
    return ledger, active
