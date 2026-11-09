"""Picker-graph geometry for slotting: ground slots, home round trips and the relocation buffer.

All distances are exact shortest paths along picker_graph edges (no rack shortcuts).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.contracts.base import exact
from app.contracts.layout import Layout
from app.navigation.shortest_paths import AllPairsPaths, UnreachableError
from app.planning.errors import PlanningInputError


@dataclass(frozen=True, slots=True)
class PlanningGeometry:
    layout_version: str
    paths: AllPairsPaths
    edge_lengths: dict[tuple[str, str], Fraction]
    service_node: dict[str, str]
    costs: dict[str, Fraction]
    homes: tuple[str, ...]
    home_node: str
    buffer_node: str

    @classmethod
    def from_layout(cls, layout: Layout) -> PlanningGeometry:
        paths = AllPairsPaths.from_graph(layout.picker_graph)
        edges: dict[tuple[str, str], Fraction] = {}
        for edge in layout.picker_graph.edges:
            edges[(edge.a, edge.b)] = edges[(edge.b, edge.a)] = exact(edge.length_m)
        service = {
            s.slot_id: s.service_node_id
            for s in layout.slots
            if s.kind == "pickface" and s.service_node_id is not None
        }
        homes = tuple(sorted(i.home_node_id for i in layout.inductions))
        _check_nodes(layout, homes, service)
        try:
            costs = {slot: _round_trip(paths, homes, node) for slot, node in service.items()}
        except UnreachableError as exc:
            raise PlanningInputError(f"ground slot unreachable from a home: {exc}") from exc
        return cls(
            layout_version=layout.layout_version,
            paths=paths,
            edge_lengths=edges,
            service_node=service,
            costs=costs,
            homes=homes,
            home_node=layout.relocation_home_node_id,
            buffer_node=layout.relocation_buffer_node_id,
        )

    def is_ground(self, slot_id: str) -> bool:
        return slot_id in self.service_node

    def slot_cost(self, slot_id: str) -> Fraction:
        """Mean home round trip in metres, homes weighted equally."""
        try:
            return self.costs[slot_id]
        except KeyError as exc:
            raise PlanningInputError(f"{slot_id} is not a ground pick-face slot") from exc

    def ground_slots_by_cost(self) -> tuple[str, ...]:
        return tuple(sorted(self.costs, key=lambda slot: (self.costs[slot], slot)))

    def distance(self, source: str, target: str) -> Fraction:
        return self.paths.require_distance(source, target)

    def path(self, source: str, target: str) -> tuple[str, ...]:
        return self.paths.path(source, target)


def _round_trip(paths: AllPairsPaths, homes: tuple[str, ...], node: str) -> Fraction:
    total = sum((2 * paths.require_distance(home, node) for home in homes), Fraction(0))
    return total / len(homes)


def _check_nodes(layout: Layout, homes: tuple[str, ...], service: dict[str, str]) -> None:
    nodes = {n.node_id for n in layout.picker_graph.nodes}
    required = {*homes, layout.relocation_home_node_id, layout.relocation_buffer_node_id}
    missing = sorted(required - nodes)
    if missing:
        raise PlanningInputError(f"picker_graph lacks required nodes {missing}")
    if not homes:
        raise PlanningInputError("layout has no induction homes")
    if layout.relocation_buffer_node_id in set(service.values()):
        raise PlanningInputError("relocation buffer must not be a slot service node")
    if not service:
        raise PlanningInputError("layout has no ground pick-face slots")
