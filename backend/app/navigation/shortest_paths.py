"""All-pairs shortest paths with exact lengths and deterministic tie-breaks.

Edge weights are exact Fractions from the layout. Dijkstra pops `(distance, node_id)`, so
equal-distance alternatives are resolved by node ID order and the result never depends on
dict iteration order.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from fractions import Fraction

from app.contracts.base import exact
from app.contracts.layout import Graph


class UnreachableError(Exception):
    """Two graph nodes are not connected."""


@dataclass(frozen=True, slots=True)
class _SourceTree:
    distance: dict[str, Fraction]
    predecessor: dict[str, str]


def _adjacency(graph: Graph) -> dict[str, tuple[tuple[str, Fraction], ...]]:
    adjacency: dict[str, list[tuple[str, Fraction]]] = {n.node_id: [] for n in graph.nodes}
    for edge in graph.edges:
        weight = exact(edge.length_m)
        adjacency[edge.a].append((edge.b, weight))
        adjacency[edge.b].append((edge.a, weight))
    return {node: tuple(sorted(links)) for node, links in adjacency.items()}


def _dijkstra(source: str, adjacency: dict[str, tuple[tuple[str, Fraction], ...]]) -> _SourceTree:
    distance: dict[str, Fraction] = {source: Fraction(0)}
    predecessor: dict[str, str] = {}
    queue: list[tuple[Fraction, str]] = [(Fraction(0), source)]
    settled: set[str] = set()
    while queue:
        dist, node = heapq.heappop(queue)
        if node in settled:
            continue
        settled.add(node)
        for neighbour, weight in adjacency[node]:
            candidate = dist + weight
            known = distance.get(neighbour)
            if known is None or candidate < known:
                distance[neighbour] = candidate
                predecessor[neighbour] = node
                heapq.heappush(queue, (candidate, neighbour))
    return _SourceTree(distance=distance, predecessor=predecessor)


@dataclass(frozen=True, slots=True)
class AllPairsPaths:
    """Exact shortest distances and canonical paths between every pair of nodes."""

    node_ids: tuple[str, ...]
    _trees: dict[str, _SourceTree]

    @classmethod
    def from_graph(cls, graph: Graph) -> AllPairsPaths:
        adjacency = _adjacency(graph)
        node_ids = tuple(sorted(adjacency))
        return cls(node_ids=node_ids, _trees={n: _dijkstra(n, adjacency) for n in node_ids})

    def distance(self, source: str, target: str) -> Fraction | None:
        """Exact shortest distance in metres, or None if the nodes are disconnected."""
        return self._tree(source).distance.get(target)

    def require_distance(self, source: str, target: str) -> Fraction:
        dist = self.distance(source, target)
        if dist is None:
            raise UnreachableError(f"{target} is not reachable from {source}")
        return dist

    def path(self, source: str, target: str) -> tuple[str, ...]:
        """Canonical node sequence from source to target, both included."""
        tree = self._tree(source)
        if target not in tree.distance:
            raise UnreachableError(f"{target} is not reachable from {source}")
        nodes = [target]
        while nodes[-1] != source:
            nodes.append(tree.predecessor[nodes[-1]])
        return tuple(reversed(nodes))

    def _tree(self, source: str) -> _SourceTree:
        try:
            return self._trees[source]
        except KeyError as exc:
            raise UnreachableError(f"unknown node {source}") from exc
