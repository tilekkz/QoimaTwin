"""Immutable cargo identities; dynamic ownership stays in events and snapshots."""

from typing import Any

from app.simulation.engine import Engine


def cargo_catalog(engine: Engine) -> list[dict[str, Any]]:
    inputs = engine.ctx.inputs
    cargo: dict[str, dict[str, Any]] = {}
    for index in range(1, inputs.config.totes_total + 1):
        cid = f"T{index:03d}"
        cargo[cid] = _cargo(cid, "tote", [], [])
    for lot in inputs.assignment.initial_lots:
        contents = [{"sku_id": lot.sku_id, "quantity": lot.quantity}]
        cargo[lot.lot_id] = _cargo(lot.lot_id, "lot", contents, [])
    orders = {o.order_id: o for o in inputs.scenario.orders}
    for event in engine.ctx.recorder.events:
        payload = event.payload
        if event.kind == "order_packed":
            order = orders[payload["order_id"]]
            cid = payload["parcel_id"]
            cargo[cid] = _cargo(
                cid,
                "parcel",
                [line.model_dump() for line in sorted(order.lines, key=lambda line: line.sku_id)],
                [order.order_id],
            )
        elif event.kind == "parcel_scanned":
            cid = payload["pallet_id"]
            cargo.setdefault(cid, _cargo(cid, "pallet", [], []))["order_ids"].append(
                payload["order_id"]
            )
        elif event.kind == "pallet_sealed":
            cid = payload["pallet_id"]
            cargo[cid] = _cargo(cid, "pallet", [], payload["order_ids"])
        elif event.kind == "receipt_accepted":
            cid = payload["pallet_id"]
            contents = [{"sku_id": payload["sku_id"], "quantity": payload["quantity"]}]
            cargo[cid] = _cargo(cid, "pallet", contents, [])
    if engine.shipping.open_pallet is not None:
        pallet = engine.shipping.open_pallet
        cargo.setdefault(pallet.pallet_id, _cargo(pallet.pallet_id, "pallet", [], []))
    return [cargo[cid] for cid in sorted(cargo)]


def _cargo(cid: str, kind: str, contents: list[Any], orders: list[str]) -> dict[str, Any]:
    return {"cargo_id": cid, "kind": kind, "contents": contents, "order_ids": orders}


def initial_state(engine: Engine) -> dict[str, Any]:
    return {
        "inventory_lots": [
            lot.model_dump(mode="json")
            for lot in sorted(engine.ctx.inputs.assignment.initial_lots, key=lambda lot: lot.lot_id)
        ],
        "tote_pool": [f"T{i:03d}" for i in range(1, engine.ctx.config.totes_total + 1)],
        "cells": {},
        "queues": {"orders": [], "shipping": [], "receiving": [], "sealed": []},
        "merge_cursors": {},
        "station_reserved_wip": dict.fromkeys(sorted(engine.packing.stations), 0),
        "pallet_state": {},
    }
