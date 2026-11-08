"""Explicit source choices; source port clocks and slot anchors are derived by the binder."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.profile_models import BufferChoice
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptOffer, ReceiptPlace, ReceiptPort
from app.v3.stock_models import StockOwner
from app.v3.stock_receipts import ReceiptDefinition
from app.v3.whole_flow_models import WholeFlowProfile, WholeHUOrder, WholeHUPort
from tests.v3.test_light_flow_source import source_profile
from tests.v3.test_receipt_flow_fixtures import SECOND


def whole_source_choices() -> tuple[WholeFlowProfile, tuple[BufferChoice, ...]]:
    flow = source_profile()
    actors = tuple(
        replace(a, home="v3:service:OUT_W_RETAIL") if a.actor_id in {"S01", "S02"} else a
        for a in flow.actors
    )
    owners = tuple(
        replace(o, kind="worker") if o.owner_id in {"actor:P01", "actor:S01"} else o
        for o in flow.owners
    )
    buffer_id = "v3:buffer:OUT_W_RETAIL:01"
    owners = (*owners, StockOwner("actor:S02", "worker", 1), StockOwner(buffer_id, "buffer", 1))
    flow = replace(
        flow,
        profile_id="explicit-whole-standard-source-v1",
        provenance=(
            "ADR0056 synthetic worker speed1m/s and pickup/place1s; no mesh hand contact proof"
        ),
        owners=owners,
        actors=actors,
        orders=(),
    )
    port = WholeHUPort("OUT_W_RETAIL", "derived", (), (), (buffer_id,), ("S01", "S02"), "shipped")
    placeholder = ReceiptPlace(buffer_id, "derived", (F(1), F(1), F(1)), F(15), F(".02"))
    order = WholeHUOrder("WHOLE-1", 0, "v3:HU:initial:DEMO_111:01", port.port_id)
    receipt = ReceiptFlowProfile(flow, (), (), (), SECOND, SECOND)
    profile = WholeFlowProfile(receipt, (order,), (port,), (placeholder,), SECOND, SECOND)
    buffer = BufferChoice(
        place_id=buffer_id,
        port_id=port.port_id,
        zone_id="STAGE_OUT_W_RETAIL",
        bounds_xz=("14", "56.5", "16", "58.5"),
        path_xz=(("6", "54"), ("6", "57.5"), ("15", "57.5")),
        height_m="1.2",
        max_payload_kg="15",
    )
    return profile, (buffer,)


def whole_source_receipt_choices() -> tuple[WholeFlowProfile, tuple[BufferChoice, ...]]:
    profile, buffers = whole_source_choices()
    flow = profile.receipts.flow
    buffer_id = "synthetic:buffer:IN_N_STANDARD:01"
    owners = (
        *flow.owners,
        StockOwner("actor:R01", "worker", 1),
        StockOwner(buffer_id, "buffer", 1),
    )
    actors = tuple(
        replace(a, home="v3:service:IN_N_STANDARD") if a.actor_id == "R01" else a
        for a in flow.actors
    )
    flow = replace(
        flow, owners=owners, actors=actors, profile_id="explicit-standard-receipt-whole-v1"
    )
    port = ReceiptPort("IN_N_STANDARD", "derived", 1, (), (buffer_id,), ("R01",))
    offer = ReceiptOffer(
        ReceiptDefinition(
            "RECEIPT-STANDARD-1", "RECEIVED-STANDARD-1", "DEMO_111", "EXPLICIT-STANDARD-LOT-1", 24
        ),
        0,
        port.port_id,
        "v3:slot:FLEX_W:001:L1:B1",
    )
    place = ReceiptPlace(buffer_id, "derived", (F(1), F(1), F(1)), F(15), F(".02"))
    receipts = replace(
        profile.receipts, flow=flow, ports=(port,), receipts=(offer,), places=(place,)
    )
    profile = replace(
        profile,
        receipts=receipts,
        orders=(replace(profile.orders[0], hu_id=offer.definition.hu_id),),
    )
    buffer = BufferChoice(
        place_id=buffer_id,
        port_id=port.port_id,
        zone_id="STAGE_IN_N_W",
        bounds_xz=("59.4", "59.4", "60.6", "60.6"),
        path_xz=(("72", "66"), ("60", "66"), ("60", "60")),
        height_m="1.2",
        max_payload_kg="15",
    )
    return profile, (*buffers, buffer)
