"""Directed candidate routes; these primitives do not grant operational admission."""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Arc:
    arc_id: str
    source: str
    target: str
    length_m: Fraction
    cost_m: Fraction
    modes: frozenset[str] = frozenset()
    profiles: frozenset[str] = frozenset()
    cargo_classes: frozenset[str] = frozenset()
    clear_width_m: Fraction | None = None
    clear_height_m: Fraction | None = None


@dataclass(frozen=True, slots=True)
class RouteRequirements:
    mode: str | None = None
    profile: str | None = None
    cargo: str | None = None
    min_clear_width_m: Fraction | None = None
    min_clear_height_m: Fraction | None = None


@dataclass(frozen=True, slots=True)
class CandidateRoute:
    graph_id: str
    node_ids: tuple[str, ...]
    arc_ids: tuple[str, ...]
    length_m: Fraction
    cost_m: Fraction


def _name(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("graph identifiers must be nonempty strings")


def _positive(value: object) -> None:
    if not isinstance(value, Fraction) or value <= 0:
        raise ValueError("graph metrics must be positive exact fractions")


def _validate_arc(arc: Arc, nodes: set[str]) -> None:
    _name(arc.arc_id)
    if arc.source not in nodes or arc.target not in nodes:
        raise ValueError("arc endpoint is absent from its graph")
    _positive(arc.length_m)
    _positive(arc.cost_m)
    for values in (arc.modes, arc.profiles, arc.cargo_classes):
        if not isinstance(values, frozenset):
            raise ValueError("arc permissions must be immutable sets")
        for value in values:
            _name(value)
    for metric in (arc.clear_width_m, arc.clear_height_m):
        if metric is not None:
            _positive(metric)


def _validate_requirements(requirements: RouteRequirements) -> None:
    for value in (requirements.mode, requirements.profile, requirements.cargo):
        if value is not None:
            _name(value)
    for metric in (requirements.min_clear_width_m, requirements.min_clear_height_m):
        if metric is not None:
            _positive(metric)


def _eligible(arc: Arc, required: RouteRequirements) -> bool:
    for value, allowed in (
        (required.mode, arc.modes),
        (required.profile, arc.profiles),
        (required.cargo, arc.cargo_classes),
    ):
        if value is not None and value not in allowed:
            return False
    for needed, available in (
        (required.min_clear_width_m, arc.clear_width_m),
        (required.min_clear_height_m, arc.clear_height_m),
    ):
        if needed is not None and (available is None or available < needed):
            return False
    return True


def _search(
    source: str, target: str, adjacency: Mapping[str, tuple[Arc, ...]], required: RouteRequirements
) -> dict[str, Arc] | None:
    distances = {source: Fraction(0)}
    previous: dict[str, Arc] = {}
    queue = [(Fraction(0), source)]
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == target:
            return previous
        for arc in adjacency[node]:
            if not _eligible(arc, required):
                continue
            candidate = distance + arc.cost_m
            known = distances.get(arc.target)
            if known is None or candidate < known:
                distances[arc.target] = candidate
                previous[arc.target] = arc
                heapq.heappush(queue, (candidate, arc.target))
    return None


def _route(graph_id: str, source: str, target: str, previous: Mapping[str, Arc]) -> CandidateRoute:
    path: list[Arc] = []
    node = target
    while node != source:
        arc = previous[node]
        path.append(arc)
        node = arc.source
    path.reverse()
    return CandidateRoute(
        graph_id,
        (source, *(arc.target for arc in path)),
        tuple(arc.arc_id for arc in path),
        sum((arc.length_m for arc in path), Fraction(0)),
        sum((arc.cost_m for arc in path), Fraction(0)),
    )


@dataclass(frozen=True, slots=True, init=False)
class DirectedGraph:
    graph_id: str
    node_ids: tuple[str, ...]
    _adjacency: Mapping[str, tuple[Arc, ...]] = field(repr=False)

    def __init__(self, graph_id: str, node_ids: Iterable[str], arcs: Iterable[Arc]) -> None:
        _name(graph_id)
        nodes = tuple(node_ids)
        for node in nodes:
            _name(node)
        node_set = set(nodes)
        if len(node_set) != len(nodes):
            raise ValueError("duplicate graph node")
        adjacency: dict[str, list[Arc]] = {node: [] for node in nodes}
        seen: set[str] = set()
        for arc in arcs:
            _validate_arc(arc, node_set)
            if arc.arc_id in seen:
                raise ValueError("duplicate directed arc")
            seen.add(arc.arc_id)
            adjacency[arc.source].append(arc)
        frozen = {
            node: tuple(sorted(outgoing, key=lambda a: (a.target, a.arc_id)))
            for node, outgoing in adjacency.items()
        }
        object.__setattr__(self, "graph_id", graph_id)
        object.__setattr__(self, "node_ids", tuple(sorted(nodes)))
        object.__setattr__(self, "_adjacency", MappingProxyType(frozen))

    def shortest_path(
        self, source: str, target: str, required: RouteRequirements | None = None
    ) -> CandidateRoute | None:
        """Filter before scoring; absent clearance never proves a requested clearance.

        The unfiltered result is geometry-only. Even a filtered candidate still
        requires handling evidence, actual worker/equipment and traffic reservations.
        """
        required = required or RouteRequirements()
        _validate_requirements(required)
        if not self._adjacency:
            return None
        if source not in self._adjacency or target not in self._adjacency:
            raise ValueError("route endpoint is absent from its graph")
        previous = _search(source, target, self._adjacency, required)
        return None if previous is None else _route(self.graph_id, source, target, previous)
