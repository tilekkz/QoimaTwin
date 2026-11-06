"""Compiled run inputs and the shared context that subsystems use."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import pairwise

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


class InputError(ValueError):
    """Run inputs are inconsistent with each other (reported as HTTP 422 by the API)."""


@dataclass(frozen=True, slots=True)
class RunInputs:
    layout: Layout
    config: SimulationConfig
    actors: ActorRegistry
    assignment: Assignment
    scenario: Scenario
    experiment_type: str = "slotting"


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
        self.sched.schedule(tick, Phase.DISPATCH, self._dispatch_hook, unique="dispatch")

    def _dispatch_hook(self) -> None:
        raise NotImplementedError  # replaced by the engine


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
