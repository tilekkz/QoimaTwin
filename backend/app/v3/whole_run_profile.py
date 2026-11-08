"""Reconstruct the declared physical profile without private adjacency or execution state."""

from collections.abc import Hashable
from typing import Any, cast

from app.v3.interface import Json
from app.v3.light_flow_models import FlowProfile
from app.v3.receipt_flow_models import ReceiptFlowProfile
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import Container, StockOwner, StockSeed, UnitToken
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_native_decode import decode


def decode_profile(value: Json) -> WholeFlowProfile:
    flow = _flow(value)
    receipt = _process(value["receipt_process"], ReceiptFlowProfile, {"flow": flow})
    return WholeFlowProfile(
        **_process_values(value["whole_process"], WholeFlowProfile, {"receipts": receipt})
    )


def _flow(value: Json) -> FlowProfile:
    graph, initial, profile = value["graph"], value["initial_state"], value["profile"]
    if set(graph) != {"graph_id", "node_ids", "arcs"}:
        raise ValueError("Whole graph contains missing or private fields")
    arcs = decode(tuple[Arc, ...], graph["arcs"])
    route = DirectedGraph(
        decode(str, graph["graph_id"]), decode(tuple[str, ...], graph["node_ids"]), arcs
    )
    units = decode(tuple[UnitToken, ...], initial["source_units"])
    ids = {u.origin_hu for u in units}
    containers = decode(tuple[Container, ...], initial["stock"]["containers"])
    stock = StockSeed(
        units,
        tuple(c for c in containers if c.container_id in ids),
        decode(tuple[StockOwner, ...], initial["source_owners"]),
    )
    return FlowProfile(**_values(profile, FlowProfile, {"graph": route, "stock": stock}))


def _values(raw: Json, cls: type[Any], supplied: Json) -> Json:
    from app.v3.receipt_run_decode import _field_types

    types = _field_types(cast(Hashable, cls))
    if raw.keys() != types.keys() - supplied.keys():
        raise ValueError("Whole materialized profile contains missing or unknown fields")
    return {**supplied, **{k: decode(types[k], v) for k, v in raw.items()}}


def _process_values(raw: Json, cls: type[Any], supplied: Json) -> Json:
    values = {k: v for k, v in raw.items() if k != "route_policy"}
    if cls is ReceiptFlowProfile:
        values["receipts"] = values.pop("offers")
    return _values(values, cls, supplied)


def _process(raw: Json, cls: type[Any], supplied: Json) -> Any:
    return cls(**_process_values(raw, cls, supplied))
