"""Typed source binding only; this is not a new public JSON/CLI admission contract."""

import hashlib
from dataclasses import dataclass, replace
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_sources import verified_records
from app.v3.flow_profile_wire import materialized_record, record
from app.v3.input_models import V3Bundle
from app.v3.light_flow_source import bind_source_profile
from app.v3.profile_build import document
from app.v3.profile_models import BufferChoice
from app.v3.runtime_graph_source import compiled_graph
from app.v3.stock_ledger import StockLedger
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_flow_validate import validate_whole_flow
from app.v3.whole_profile_binding import bind_ports, bind_slots, check_modules, source_classes
from app.v3.whole_profile_geometry import ROUTE_POLICY, bind_buffers, project_whole_manual_cargo

__all__ = ["BoundWholeSource", "bind_whole_source", "project_whole_manual_cargo"]
WHOLE_SOURCE_VERSION = "qoima-whole-flow-source-proposal-1"


@dataclass(frozen=True, slots=True)
class BoundWholeSource:
    profile: WholeFlowProfile
    graph_document: bytes
    frozen_bytes: bytes
    input_hash: str


def bind_whole_source(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    choices: WholeFlowProfile,
    buffers: tuple[BufferChoice, ...],
) -> BoundWholeSource:
    sources = verified_records(bundle, conveyor)
    if type(choices) is not WholeFlowProfile:
        raise ValueError("Exact typed whole profile required")
    profile, links = _bind(bundle, conveyor, choices, buffers)
    ledger = validate_whole_flow(profile, conveyor)
    frozen = _freeze(profile, links, buffers, sources, ledger)
    return BoundWholeSource(
        profile, canonical_bytes(links), frozen, hashlib.sha256(frozen).hexdigest()
    )


def _bind(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    choices: WholeFlowProfile,
    buffers: tuple[BufferChoice, ...],
) -> tuple[WholeFlowProfile, dict[str, Any]]:
    flow = choices.receipts.flow
    baseline = bind_source_profile(bundle, conveyor, replace(flow, orders=()))
    if (flow.source_revision, flow.source_hashes) != (
        baseline.source_revision,
        baseline.source_hashes,
    ):
        raise ValueError("Whole choices must bind the exact source revision/fingerprints")
    classes = source_classes(bundle, choices)
    inbound, outbound = bind_ports(bundle, choices, classes)
    receive_slots, source_slots = bind_slots(bundle, choices, classes)
    check_modules(bundle, choices)
    links = document(bundle, "layout-links-v3.json")
    project_whole_manual_cargo(links)
    buffer_places = bind_buffers(bundle, choices, buffers, links)
    orders = bind_source_profile(bundle, conveyor, flow).orders
    flow = replace(baseline, graph=compiled_graph(links, "walk"), orders=orders)
    receipt_buffers = tuple(buffer_places[k] for p in inbound for k in p.buffer_ids)
    whole_buffers = tuple(buffer_places[k] for p in outbound for k in p.buffer_ids)
    receipts = replace(
        choices.receipts, flow=flow, ports=inbound, places=(*receive_slots, *receipt_buffers)
    )
    profile = replace(
        choices, receipts=receipts, ports=outbound, places=(*source_slots, *whole_buffers)
    )
    return profile, links


def _freeze(
    profile: WholeFlowProfile,
    links: dict[str, Any],
    buffers: tuple[BufferChoice, ...],
    sources: dict[str, Any],
    ledger: StockLedger,
) -> bytes:
    receipts = profile.receipts
    return canonical_bytes(
        {
            "compiler_version": WHOLE_SOURCE_VERSION,
            "scope": "bounded_source_manual_whole_hu_typed_proposal",
            "route_policy": ROUTE_POLICY,
            **sources,
            **materialized_record(receipts.flow, ledger),
            "initial_inventory": record(ledger.inventory_snapshot()),
            "receipt_process": {
                "ports": record(receipts.ports),
                "places": record(receipts.places),
                "offers": record(receipts.receipts),
                "pickup_tick": receipts.pickup_tick,
                "place_tick": receipts.place_tick,
            },
            "whole_process": {
                "ports": record(profile.ports),
                "places": record(profile.places),
                "orders": record(profile.orders),
                "pickup_tick": profile.pickup_tick,
                "place_tick": profile.place_tick,
            },
            "local_connectors": [b.model_dump() for b in buffers],
            "graph_document": links,
        }
    )
