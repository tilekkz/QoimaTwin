"""Pinned C08/L07/L11/L12 adapter; raw source bytes remain available and immutable."""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from app.storage.canonical_json import parse_json

from .input_pin import LAYOUT_CONTENT_HASH, LAYOUT_VERSION, SOURCE_REVISION
from .runtime_graph_source import _object
from .vehicle_graph import decode_vehicle_graph
from .vehicle_handling import HandlingDesign, decode_handling_design
from .vehicle_types import VehicleGraph

__all__ = [
    "PINNED_SHA256",
    "SOURCE_REVISION",
    "VehicleAdapter",
    "load_vehicle_adapter",
    "verified_json",
]

PINNED_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "layout-links-v3.json": "c1fb96d2a72d29d66932ff4de0213b0bf4ebc0abd92102052f6c6ba841942d65",
        "layout-conflicts-v3.json": (
            "7007d809982f5df117dbd93cdec89005b69fdadad8d352285994048f03c2e917"
        ),
        "vehicle-handling-v3.json": (
            "22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4"
        ),
        "vehicle-graph-v3.json": "be17461061cc33fe07540d0bc5572f61ce74ac9852198ee5423ed549deb3f832",
        "storage-slots-v3.json": "09ebe5d0d8f41ce0eea5180a04b6e53c1965a9bfdd4eaa04ce324b2c6cb89681",
        "port-resource-policy-v3.json": (
            "0b462fb24d8f783282c9c1e415af6456a0e60455f1a5c562c9208551d0223e9b"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class VehicleAdapter:
    source_revision: str
    source_hashes: tuple[tuple[str, str], ...]
    graph: VehicleGraph
    handling: HandlingDesign
    raw_documents: Mapping[str, bytes]

    @property
    def operational_admission(self) -> Literal[False]:
        return False

    def declared_loaded_arc(self, arc_id: str, cargo_id: str, pair_id: str) -> bool:
        """Intersect source permissions only; this is never an actual motion grant."""
        arc = self.graph.arcs.get(arc_id)
        load = next((load for load in self.handling.loads if load.cargo_id == cargo_id), None)
        if arc is None or load is None:
            return False
        return (
            arc_id in load.allowed_arc_ids
            and cargo_id in arc.cargo_classes
            and pair_id in arc.equipment_pairs
            and bool(arc.profiles & {load.local_profile, "loaded_max"})
        )


def verified_json(raw: bytes, expected_sha256: str) -> Mapping[str, object]:
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("vehicle source SHA256 mismatch")
    return _object(parse_json(raw))


def _validate_design(graph: VehicleGraph, design: HandlingDesign) -> None:
    arc_ids = set(graph.arcs)
    for load in design.loads:
        if not load.allowed_arc_ids <= arc_ids:
            raise ValueError("C08 cargo eligibility refers to an unknown compiled arc")
    for slot in design.slots:
        if slot.vehicle_node_id is not None and slot.vehicle_node_id not in graph.nodes:
            raise ValueError("source slot refers to an unknown vehicle prehandling pose")
    pairs = {pair[0] for pair in design.pairs}
    if any(not arc.equipment_pairs <= pairs for arc in graph.arcs.values()):
        raise ValueError("graph equipment pair is absent from fixed source policy")


def load_vehicle_adapter(source_root: Path) -> VehicleAdapter:
    """Read the six exact files below docs/v3/contract-proposals at the pinned revision."""
    raw_documents: dict[str, bytes] = {}
    for name in PINNED_SHA256:
        try:
            raw = (source_root / "docs/v3/contract-proposals" / name).read_bytes()
        except OSError as exc:
            raise ValueError(f"required vehicle source unreadable: {name}") from exc
        raw_documents[name] = raw
    return _decode_adapter(raw_documents)


def _decode_adapter(raw_documents: Mapping[str, bytes]) -> VehicleAdapter:
    if set(raw_documents) != set(PINNED_SHA256):
        raise ValueError("vehicle adapter requires exactly six source documents")
    documents = {
        name: verified_json(raw_documents[name], expected)
        for name, expected in PINNED_SHA256.items()
    }
    graph = decode_vehicle_graph(
        documents["layout-links-v3.json"],
        documents["layout-conflicts-v3.json"],
        documents["vehicle-graph-v3.json"],
    )
    handling = documents["vehicle-handling-v3.json"]
    if (
        graph.layout_version != LAYOUT_VERSION
        or handling.get("layout_content_hash") != LAYOUT_CONTENT_HASH
    ):
        raise ValueError("vehicle source layout binding mismatch")
    design = decode_handling_design(
        handling, documents["storage-slots-v3.json"], documents["port-resource-policy-v3.json"]
    )
    _validate_design(graph, design)
    return VehicleAdapter(
        SOURCE_REVISION,
        tuple(sorted(PINNED_SHA256.items())),
        graph,
        design,
        MappingProxyType(dict(raw_documents)),
    )
