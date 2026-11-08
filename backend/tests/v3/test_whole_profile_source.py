"""Pinned whole source facts and denied cargo permissions are fixed before source execution."""

import copy
from typing import Any

from app.v3.whole_profile_source import bind_whole_source, project_whole_manual_cargo
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_whole_profile_fixtures import whole_source_choices, whole_source_receipt_choices


def test_whole_projection_is_absent_only_and_preserves_explicit_denials() -> None:
    rows: list[dict[str, Any]] = [
        {"allowed_modes": ["pedestrian"]},
        {"allowed_modes": ["pedestrian"], "cargo_transport_supported": False},
        {"allowed_modes": ["pedestrian"], "allowed_cargo_archetype_ids": []},
        {"allowed_modes": ["pedestrian"], "allowed_cargo_archetype_ids": ["SMALL_CARTON"]},
        {"allowed_modes": ["forklift"]},
    ]
    before = copy.deepcopy(rows)
    links = {"walk_graph": {"arcs": rows}}
    project_whole_manual_cargo(links)
    assert rows[0]["allowed_cargo_archetype_ids"] == ["SMALL_CARTON", "STANDARD_CARTON"]
    assert rows[0]["cargo_transport_supported"] is True
    assert rows[1:] == before[1:]


def test_actual_source_original_standard_binds_all_stock_and_finite_out_w_cell() -> None:
    choices, buffers = whole_source_choices()
    bound = bind_whole_source(source_bundle(), source_catalog(), choices, buffers)
    flow = bound.profile.receipts.flow
    assert len(flow.stock.containers) == 530 and len(flow.stock.units) == 12256
    assert len(flow.actors) == 24
    port = bound.profile.ports[0]
    assert port.node_id == "v3:service:OUT_W_RETAIL"
    assert port.service_ticks == (("SMALL_CARTON", 25_000_000), ("STANDARD_CARTON", 35_000_000))
    assert port.windows == ((0, 28_800_000_000),)
    places = {p.owner_id: p for p in bound.profile.places}
    assert (
        places["v3:slot:STANDARD_E:007:L1:B2"].node_id == "v3:module:STANDARD_E:007:B2:worker:node"
    )
    assert places[port.buffer_ids[0]].node_id != port.node_id
    assert b'"connector_provenance"' in bound.graph_document
    assert b'"_adjacency"' not in bound.frozen_bytes and b'"history"' not in bound.frozen_bytes


def test_standard_receipt_uses_real_in_n_service_free_flex_slot_and_future_ancestry() -> None:
    from app.v3.whole_flow_engine import WholeFlowEngine

    choices, buffers = whole_source_receipt_choices()
    bound = bind_whole_source(source_bundle(), source_catalog(), choices, buffers)
    receipt = bound.profile.receipts
    assert receipt.ports[0].service_tick == 18_000_000
    assert receipt.ports[0].node_id == "v3:service:IN_N_STANDARD"
    slot = next(p for p in receipt.places if p.owner_id == "v3:slot:FLEX_W:001:L1:B1")
    assert slot.node_id == "v3:module:FLEX_W:001:B1:worker:node"
    assert bound.profile.orders[0].hu_id == "RECEIVED-STANDARD-1"
    engine = WholeFlowEngine(bound.profile, source_catalog())
    assert len(engine.ledger.inventory_snapshot().locations) == 12256
    assert engine.ledger.inventory_snapshot().registered_receipts == ()
