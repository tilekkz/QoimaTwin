"""Explicit receipt choices derived from declared source/example facts before execution."""

import json
from fractions import Fraction
from pathlib import Path
from typing import Any


def ratio(value: str) -> dict[str, int]:
    exact = Fraction(value)
    return {"numerator": exact.numerator, "denominator": exact.denominator}


def receipt_choices() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    value: dict[str, Any] = json.loads(
        (root / "docs/proposals/adaptive-v3/light-flow-profile.example.json").read_bytes()
    )
    value.update(
        schema_id="qoima.receipt-flow-profile.v3-proposal",
        profile_id="explicit-received-small-three-units-v1",
        horizon_tick=1_200_000_000,
        end_tick=2_400_000_000,
    )
    value["provenance"] = (
        "ADR0052 explicit receipt, source slot and synthetic material/handling choices"
    )
    value["owners"].extend(
        [
            {"owner_id": "actor:R01", "kind": "worker", "capacity": 1},
            {"owner_id": "synthetic:buffer:IN_E_PARCEL:01", "kind": "buffer", "capacity": 1},
        ]
    )
    value["receipt_ports"] = [
        {
            "port_id": "IN_E_PARCEL",
            "receiver_ids": ["R01"],
            "buffer_owner_ids": ["synthetic:buffer:IN_E_PARCEL:01"],
        }
    ]
    value["receipt_buffers"] = [buffer_choices()]
    value["receipt_times"] = {"pickup": 1_000_000, "place": 1_000_000}
    value["receipts"] = [receipt_definition()]
    for actor in value["actors"]:
        if actor["actor_id"] == "R01":
            actor["home"] = "v3:service:IN_E_PARCEL"
    for order in value["orders"]:
        order["source_hu"] = "RECEIVED-SMALL-1"
        for key in ("carrier_placements", "package_placements"):
            for ordinal, placement in enumerate(order[key], 1):
                placement["unit_id"] = f"RECEIVED-SMALL-1:unit:{ordinal:04d}"
    return value


def receipt_definition() -> dict[str, Any]:
    return {
        "receipt_id": "RECEIPT-1",
        "hu_id": "RECEIVED-SMALL-1",
        "sku_id": "DEMO_001",
        "lot_id": "EXPLICIT-RECEIPT-LOT-1",
        "quantity_units": 24,
        "arrival_tick": 0,
        "port_id": "IN_E_PARCEL",
        "slot_id": "v3:slot:SMALL_W:017:L1:B1",
    }


def buffer_choices() -> dict[str, Any]:
    return {
        "owner_id": "synthetic:buffer:IN_E_PARCEL:01",
        "port_id": "IN_E_PARCEL",
        "zone_id": "STAGE_IN_E_PARCEL",
        "bounds_xz": [ratio(v) for v in ("129.4", "58.4", "130.6", "59.6")],
        "path_xz": [
            [ratio(x), ratio(z)]
            for x, z in (("138", "54"), ("138", "63"), ("130", "63"), ("130", "59"))
        ],
        "height_m": ratio("1.2"),
        "max_gross_kg": ratio("15"),
        "clearance_m": ratio(".005"),
    }
