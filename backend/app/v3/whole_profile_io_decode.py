"""Decode caller choices; only the existing source binder can grant physical admission."""

from dataclasses import replace
from typing import Any

from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_decode import decode_choices, rational
from app.v3.input_models import V3Bundle
from app.v3.light_flow_source import bind_source_profile
from app.v3.profile_models import BufferChoice
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptPlace, ReceiptPort
from app.v3.receipt_profile_geometry import _buffer
from app.v3.receipt_profile_source import _offers
from app.v3.whole_flow_models import WholeFlowProfile, WholeHUOrder, WholeHUPort


def decode(
    bundle: V3Bundle, conveyor: ConveyorSource, value: dict[str, Any]
) -> tuple[WholeFlowProfile, tuple[BufferChoice, ...]]:
    choices = decode_choices(value)
    baseline = bind_source_profile(bundle, conveyor, replace(choices, orders=()))
    flow = replace(baseline, orders=choices.orders)
    receipts = ReceiptFlowProfile(
        flow,
        tuple(
            ReceiptPort(
                p["port_id"],
                "derived",
                1,
                (),
                tuple(p["buffer_owner_ids"]),
                tuple(p["receiver_ids"]),
            )
            for p in value["receipt_ports"]
        ),
        _places(value["receipt_buffers"]),
        _offers(value),
        value["receipt_times"]["pickup"],
        value["receipt_times"]["place"],
    )
    profile = WholeFlowProfile(
        receipts,
        tuple(WholeHUOrder(**row) for row in value["whole_orders"]),
        _ports(value),
        _places(value["whole_buffers"]),
        value["whole_times"]["pickup"],
        value["whole_times"]["place"],
    )
    buffers = sorted(
        (*value["receipt_buffers"], *value["whole_buffers"]), key=lambda row: row["owner_id"]
    )
    return profile, tuple(_buffer(row) for row in buffers)


def _ports(value: dict[str, Any]) -> tuple[WholeHUPort, ...]:
    return tuple(
        WholeHUPort(
            p["port_id"],
            "derived",
            (),
            (),
            tuple(p["buffer_owner_ids"]),
            tuple(p["shipper_ids"]),
            p["shipped_owner"],
        )
        for p in value["whole_ports"]
    )


def _places(rows: list[dict[str, Any]]) -> tuple[ReceiptPlace, ...]:
    result = []
    for row in rows:
        x0, z0, x1, z1 = (rational(v) for v in row["bounds_xz"])
        result.append(
            ReceiptPlace(
                row["owner_id"],
                "derived",
                (x1 - x0, rational(row["height_m"]), z1 - z0),
                rational(row["max_gross_kg"]),
                rational(row["clearance_m"]),
            )
        )
    return tuple(result)
