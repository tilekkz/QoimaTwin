"""Prospective receipt validation never inserts future units into the live seed."""

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction

from app.v3.belt_plan import valid_tick
from app.v3.conveyor_models import ConveyorSource
from app.v3.light_flow_inputs import _handoff_inputs
from app.v3.light_flow_models import FlowProfile
from app.v3.light_flow_validate import _orders, _validate
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptOffer, ReceiptPlace, ReceiptPort
from app.v3.receipt_flow_plan import receipt_plan, wrapper_recipe
from app.v3.stock_claims import identity
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockOwner
from app.v3.stock_receipts import validate_receipt
from app.v3.stock_validation import exact, require, vector

UnitValidator = Callable[[FlowProfile, ConveyorSource, StockLedger], None]


def validate_receipt_flow(profile: ReceiptFlowProfile, conveyor: ConveyorSource) -> StockLedger:
    return _validate_receipts(profile, conveyor, "workstation", frozenset({"SMALL_CARTON"}))


def _validate_receipts(
    profile: ReceiptFlowProfile,
    conveyor: ConveyorSource,
    actor_kind: str,
    archetypes: frozenset[str],
    *,
    unit_validator: UnitValidator = _orders,
    picker_home_at_cart: bool = True,
) -> StockLedger:
    require(type(profile) is ReceiptFlowProfile, "typed receipt-flow profile required")
    live = _validate(
        replace(profile.flow, orders=()),
        conveyor,
        actor_kind,
        picker_home_at_cart=picker_home_at_cart,
    )
    _handoff_inputs(profile.flow, conveyor, actor_kind, picker_home_at_cart=picker_home_at_cart)
    for duration in (profile.pickup_tick, profile.place_tick):
        require(valid_tick(duration) and duration > 0, "positive receipt handling duration")
    owners = {o.owner_id: o for o in profile.flow.stock.owners + profile.flow.owners}
    _places(profile, owners)
    _ports(profile, owners)
    prospective = StockLedger(
        profile.flow.stock, owners=profile.flow.owners, materials=profile.flow.materials
    )
    seen = {order.order_id for order in profile.flow.orders}
    for offer in profile.receipts:
        require(type(offer) is ReceiptOffer, "typed receipt offer required")
        validate_receipt(offer.definition)
        require(offer.definition.receipt_id not in seen, "duplicate job/receipt identity")
        seen.add(offer.definition.receipt_id)
        _offer(profile, offer, owners, archetypes)
        port = next(p for p in profile.ports if p.port_id == offer.port_id)
        key = offer.definition.receipt_id
        prospective.receive_hu(
            key + ":preflight-receive",
            prospective.revision,
            offer.definition,
            "actor:" + port.receiver_ids[0],
        )
        prospective.transfer_whole_hu(
            key + ":preflight-place",
            prospective.revision,
            offer.definition.hu_id,
            offer.slot_owner_id,
        )
    _order_sources(profile)
    unit_validator(profile.flow, conveyor, prospective)
    return live


def _places(profile: ReceiptFlowProfile, owners: dict[str, StockOwner]) -> None:
    require(type(profile.places) is tuple, "immutable receipt places required")
    require(all(type(p) is ReceiptPlace for p in profile.places), "typed receipt places required")
    require(
        len({p.owner_id for p in profile.places}) == len(profile.places), "duplicate receipt place"
    )
    for place in profile.places:
        require(type(place) is ReceiptPlace, "typed receipt place required")
        identity(place.owner_id)
        require(place.node_id in profile.flow.graph.node_ids, "unknown receipt place node")
        require(place.owner_id in owners, "unknown receipt place owner")
        owner = owners[place.owner_id]
        require(
            owner.kind in {"slot", "buffer"} and owner.capacity == 1,
            "receipt place must be one physical cell",
        )
        vector(place.dimensions)
        exact(place.max_gross_kg, positive=True)
        exact(place.clearance_m)


def _ports(profile: ReceiptFlowProfile, owners: dict[str, StockOwner]) -> None:
    require(type(profile.ports) is tuple, "immutable receipt ports required")
    require(all(type(p) is ReceiptPort for p in profile.ports), "typed receipt ports required")
    require(len({p.port_id for p in profile.ports}) == len(profile.ports), "duplicate receipt port")
    places = {p.owner_id: p for p in profile.places}
    for port in profile.ports:
        require(type(port) is ReceiptPort, "typed receipt port required")
        identity(port.port_id)
        require(port.node_id in profile.flow.graph.node_ids, "unknown receipt port node")
        require(valid_tick(port.service_tick) and port.service_tick > 0, "positive receipt service")
        _windows(port)
        require(type(port.buffer_ids) is tuple and bool(port.buffer_ids), "explicit finite buffers")
        require(len(set(port.buffer_ids)) == len(port.buffer_ids), "duplicate port buffer")
        for key in port.buffer_ids:
            require(key in places and owners[key].kind == "buffer", "unknown port buffer")
            require(places[key].node_id != port.node_id, "service point cannot be a staging buffer")
        require(
            type(port.receiver_ids) is tuple and bool(port.receiver_ids), "explicit receiver IDs"
        )
        require(len(set(port.receiver_ids)) == len(port.receiver_ids), "duplicate receiver")
        require(set(port.receiver_ids) <= {"R01", "R02"}, "source receiver pool required")
        for actor in port.receiver_ids:
            require("actor:" + actor in owners, "missing receiver custody owner")
            owner = owners["actor:" + actor]
            require(owner.kind == "worker" and owner.capacity == 1, "exclusive receiver custody")


def _windows(port: ReceiptPort) -> None:
    require(type(port.windows) is tuple and bool(port.windows), "explicit receipt windows")
    previous = 0
    for value in port.windows:
        require(type(value) is tuple and len(value) == 2, "typed receipt window")
        start, end = value
        require(
            valid_tick(start) and valid_tick(end) and previous <= start < end,
            "ordered receipt windows",
        )
        previous = end


def _offer(
    profile: ReceiptFlowProfile,
    offer: ReceiptOffer,
    owners: dict[str, StockOwner],
    archetypes: frozenset[str],
) -> None:
    require(valid_tick(offer.arrival_tick), "nonnegative integer receipt arrival")
    ports, places = {p.port_id: p for p in profile.ports}, {p.owner_id: p for p in profile.places}
    require(offer.port_id in ports, "unknown receipt port")
    require(
        offer.slot_owner_id in places and owners[offer.slot_owner_id].kind == "slot",
        "known target slot",
    )
    cargo = wrapper_recipe(profile, offer)
    require(
        len(cargo.allowed_archetypes) == 1 and cargo.allowed_archetypes[0] in archetypes,
        "only SMALL receipt execution supported"
        if archetypes == frozenset({"SMALL_CARTON"})
        else "only SMALL/STANDARD receipt execution supported",
    )
    port, slot = ports[offer.port_id], places[offer.slot_owner_id]
    actors = {a.actor_id: a for a in profile.flow.actors}
    for place in (slot, *(places[key] for key in port.buffer_ids)):
        require(cargo.max_gross_kg <= place.max_gross_kg, "receipt place payload")
        require(
            all(
                d + 2 * place.clearance_m <= bound
                for d, bound in zip(cargo.outer, place.dimensions, strict=True)
            ),
            "receipt place dimensions",
        )
    for actor_id in port.receiver_ids:
        require(
            cargo.max_gross_kg <= min(Fraction(15), actors[actor_id].max_gross_kg),
            "receiver whole-HU payload",
        )
        for buffer_id in port.buffer_ids:
            receipt_plan(profile, offer, port, places[buffer_id], actors[actor_id])


def _order_sources(profile: ReceiptFlowProfile) -> None:
    require(type(profile.receipts) is tuple, "immutable receipt offers required")
    offered = {o.definition.hu_id: o for o in profile.receipts}
    places = {p.owner_id: p for p in profile.places}
    for order in profile.flow.orders:
        if order.source_hu in offered:
            slot = places[offered[order.source_hu].slot_owner_id]
            require(
                order.source_node == slot.node_id, "future order source anchor differs from putaway"
            )
