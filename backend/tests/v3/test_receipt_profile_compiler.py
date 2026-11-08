"""Receipt compilation preserves source stock and derives future putaway anchors."""

import copy
import hashlib
import json
from dataclasses import replace
from fractions import Fraction as F

from app.v3.receipt_profile import compile_receipt_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_receipt_profile_fixtures import receipt_choices


def test_receipt_compiles_with_clean_baseline_and_explicit_future_stock() -> None:
    value = receipt_choices()
    before = copy.deepcopy(value)
    result = compile_receipt_profile(source_bundle(), source_catalog(), value)
    flow = result.profile.flow
    assert len(flow.stock.units) == 12256 and len(flow.stock.containers) == 530
    assert len(flow.actors) == 24 and flow.source_revision == source_bundle().source_revision
    assert flow.orders[0].source_node == "v3:module:SMALL_W:017:B1:worker:node"
    assert flow.orders[0].cart_source_node == "v3:module:SMALL_W:017:B1:cart:node"
    port = result.profile.ports[0]
    assert port.service_tick == 10_000_000 and port.windows == ((0, 28_800_000_000),)
    assert port.receiver_ids == ("R01",)
    places = {p.owner_id: p for p in result.profile.places}
    assert places[port.buffer_ids[0]].node_id != port.node_id
    slot = places["v3:slot:SMALL_W:017:L1:B1"]
    assert slot.dimensions == (F(".42"), F(".35"), F(".42"))
    assert slot.clearance_m == F(".03") and slot.max_gross_kg == 15
    assert result.profile.receipts[0].definition.quantity_units == 24
    frozen = json.loads(result.frozen_bytes)
    assert len(frozen["initial_state"]["stock"]["locations"]) == 12256
    assert frozen["initial_inventory"]["registered_receipts"] == []
    assert frozen["initial_inventory"]["claims"] == []
    assert result.input_hash == hashlib.sha256(result.frozen_bytes).hexdigest()
    assert result.horizon_tick == 1_200_000_000 and result.end_tick == 2_400_000_000
    assert b'"history"' not in result.frozen_bytes and b"_adjacency" not in result.frozen_bytes
    assert value == before


def test_receipt_buffer_extends_only_declared_small_cargo_paths() -> None:
    from app.v3.profile_build import document as source_document
    from app.v3.receipt_profile_source import bind_receipt_profile
    from app.v3.runtime_graph import RouteRequirements
    from app.v3.runtime_graph_source import compiled_graph

    bundle = source_bundle()
    profile = bind_receipt_profile(bundle, source_catalog(), receipt_choices())
    source = compiled_graph(source_document(bundle, "layout-links-v3.json"), "walk")
    actual = {arc.arc_id: arc for arc in profile.flow.graph.arcs}
    for arc in source.arcs:
        projected = frozenset({"SMALL_CARTON"}) if "pedestrian" in arc.modes else arc.cargo_classes
        assert actual[arc.arc_id] == replace(arc, cargo_classes=projected)
    port = profile.ports[0]
    buffer = next(place for place in profile.places if place.owner_id in port.buffer_ids)
    required = RouteRequirements(mode="pedestrian", cargo="SMALL_CARTON")
    forward = profile.flow.graph.shortest_path(port.node_id, buffer.node_id, required)
    reverse = profile.flow.graph.shortest_path(buffer.node_id, port.node_id, required)
    assert forward is not None and reverse is not None
    assert forward.length_m == reverse.length_m == 9 + 8 + 4
    assert set(forward.arc_ids).isdisjoint(reverse.arc_ids)
    heavy = RouteRequirements(mode="pedestrian", cargo="HEAVY_BOX")
    assert profile.flow.graph.shortest_path(port.node_id, buffer.node_id, heavy) is None


def test_unordered_receipt_tables_and_equivalent_ratios_have_one_identity() -> None:
    first = receipt_choices()
    other = copy.deepcopy(first)
    other["actors"].reverse()
    other["owners"].reverse()
    other["receipt_buffers"][0]["height_m"] = {"numerator": 12, "denominator": 10}
    a = compile_receipt_profile(source_bundle(), source_catalog(), first)
    b = compile_receipt_profile(source_bundle(), source_catalog(), other)
    assert a.frozen_bytes == b.frozen_bytes and a.input_hash == b.input_hash
