"""New-version admission reuses the same stock and receipt authority, without precredit."""

from dataclasses import replace
from fractions import Fraction

from app.v3.belt_plan import valid_tick
from app.v3.conveyor_models import ConveyorSource
from app.v3.light_flow_validate import _orders as _unit_orders
from app.v3.receipt_flow_models import ReceiptPlace, ReceiptPort
from app.v3.receipt_flow_validate import UnitValidator, _places, _validate_receipts, _windows
from app.v3.stock_claims import identity
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container, StockOwner
from app.v3.stock_validation import require
from app.v3.whole_flow_models import (
    MANUAL_WHOLE_CLASSES,
    WholeFlowProfile,
    WholeHUOrder,
    WholeHUPort,
)
from app.v3.whole_flow_plan import whole_plan


def validate_whole_flow(profile: WholeFlowProfile, conveyor: ConveyorSource) -> StockLedger:
    return _validate_whole_flow(profile, conveyor)


def _validate_whole_flow(
    profile: WholeFlowProfile,
    conveyor: ConveyorSource,
    *,
    unit_validator: UnitValidator = _unit_orders,
    picker_home_at_cart: bool = True,
) -> StockLedger:
    require(type(profile) is WholeFlowProfile, "typed whole-flow profile required")
    live = _validate_receipts(
        profile.receipts,
        conveyor,
        "worker",
        MANUAL_WHOLE_CLASSES,
        unit_validator=unit_validator,
        picker_home_at_cart=picker_home_at_cart,
    )
    for value in (profile.pickup_tick, profile.place_tick):
        require(valid_tick(value) and value > 0, "positive whole handling duration")
    flow = profile.receipts.flow
    owners = {o.owner_id: o for o in flow.stock.owners + flow.owners}
    _places(replace(profile.receipts, places=profile.places), owners)
    _ports(profile, owners)
    prospective = _prospective(profile)
    _orders(profile, prospective, owners)
    return live


def _prospective(profile: WholeFlowProfile) -> StockLedger:
    flow = profile.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    for offer in profile.receipts.receipts:
        key = offer.definition.receipt_id
        port = next(p for p in profile.receipts.ports if p.port_id == offer.port_id)
        ledger.receive_hu(
            key + ":receive", ledger.revision, offer.definition, "actor:" + port.receiver_ids[0]
        )
        ledger.transfer_whole_hu(
            key + ":place", ledger.revision, offer.definition.hu_id, offer.slot_owner_id
        )
    return ledger


def _ports(profile: WholeFlowProfile, owners: dict[str, StockOwner]) -> None:
    require(type(profile.ports) is tuple, "immutable whole ports required")
    require(all(type(p) is WholeHUPort for p in profile.ports), "typed whole port")
    require(len({p.port_id for p in profile.ports}) == len(profile.ports), "duplicate whole port")
    places = {p.owner_id: p for p in profile.places}
    flow = profile.receipts.flow
    for port in profile.ports:
        identity(port.port_id)
        require(port.node_id in flow.graph.node_ids, "unknown whole port node")
        _windows(ReceiptPort(port.port_id, port.node_id, 1, port.windows, (), ()))
        _service(port)
        _port_resources(port, places, owners)
        if port.port_id == flow.port.port_id:
            require(
                (port.node_id, port.windows) == (flow.port.node, flow.port.windows),
                "shared port authority mismatch",
            )


def _service(port: WholeHUPort) -> None:
    require(
        type(port.service_ticks) is tuple and bool(port.service_ticks),
        "explicit whole service table",
    )
    require(
        all(type(row) is tuple and len(row) == 2 for row in port.service_ticks), "typed service row"
    )
    require(len(dict(port.service_ticks)) == len(port.service_ticks), "duplicate service class")
    require(
        all(k in MANUAL_WHOLE_CLASSES and valid_tick(v) and v > 0 for k, v in port.service_ticks),
        "supported whole service classes and positive durations required",
    )


def _port_resources(
    port: WholeHUPort, places: dict[str, ReceiptPlace], owners: dict[str, StockOwner]
) -> None:
    require(type(port.buffer_ids) is tuple and bool(port.buffer_ids), "explicit whole buffers")
    require(len(set(port.buffer_ids)) == len(port.buffer_ids), "duplicate whole buffer")
    for key in port.buffer_ids:
        require(key in places and owners[key].kind == "buffer", "unknown whole buffer")
        require(places[key].node_id != port.node_id, "port service cannot stage a HU")
    require(type(port.shipper_ids) is tuple and bool(port.shipper_ids), "explicit shippers")
    require(
        len(set(port.shipper_ids)) == len(port.shipper_ids)
        and set(port.shipper_ids) <= {"S01", "S02"},
        "unique source shipper pool required",
    )
    for key in port.shipper_ids:
        owner = owners.get("actor:" + key)
        require(
            owner is not None and owner.kind == "worker" and owner.capacity == 1,
            "exclusive shared actor custody",
        )
    require(
        port.shipped_owner in owners and owners[port.shipped_owner].kind == "shipped",
        "whole shipped owner required",
    )


def _orders(profile: WholeFlowProfile, ledger: StockLedger, owners: dict[str, StockOwner]) -> None:
    require(type(profile.orders) is tuple, "immutable whole orders required")
    flow = profile.receipts.flow
    jobs = {o.order_id for o in flow.orders} | {
        r.definition.receipt_id for r in profile.receipts.receipts
    }
    hus = {o.source_hu for o in flow.orders}
    for order in profile.orders:
        require(type(order) is WholeHUOrder, "typed whole order required")
        identity(order.job_id)
        require(
            order.job_id not in jobs and order.hu_id not in hus,
            "duplicate/conflicting whole job or HU promise",
        )
        jobs.add(order.job_id)
        hus.add(order.hu_id)
        require(valid_tick(order.arrival_tick), "integer whole arrival required")
        _order(profile, order, ledger, owners)


def _order(
    profile: WholeFlowProfile,
    order: WholeHUOrder,
    ledger: StockLedger,
    owners: dict[str, StockOwner],
) -> None:
    ports = {p.port_id: p for p in profile.ports}
    places = {p.owner_id: p for p in profile.places}
    actors = {a.actor_id: a for a in profile.receipts.flow.actors}
    require(order.port_id in ports, "unknown whole outbound port")
    contents = ledger.contents(order.hu_id)
    cargo = contents.container.recipe
    require(
        cargo.kind == "source_wrapper"
        and len(cargo.allowed_archetypes) == 1
        and cargo.allowed_archetypes[0] in MANUAL_WHOLE_CLASSES,
        "unsupported whole-HU capability",
    )
    source_owner = contents.container.owner_id
    require(
        source_owner in places and owners[source_owner].kind == "slot",
        "whole source requires exact slot anchor",
    )
    port = ports[order.port_id]
    require(
        cargo.allowed_archetypes[0] in dict(port.service_ticks),
        "whole class not served by port",
    )
    for place in (places[source_owner], *(places[k] for k in port.buffer_ids)):
        _fit(contents.container, place.dimensions, place.clearance_m, place.max_gross_kg)
    claim = ledger.reserve_hu(
        "preflight:" + order.job_id, order.job_id, ledger.revision, order.hu_id
    )
    ledger.release_claim(claim.claim_id, order.job_id)
    for key in port.shipper_ids:
        require(
            contents.gross_mass_kg <= min(Fraction(15), actors[key].max_gross_kg),
            "whole handler payload",
        )
        for buffer in port.buffer_ids:
            whole_plan(
                profile, order, cargo, places[source_owner], places[buffer], port, actors[key]
            )


def _fit(
    container: Container,
    dimensions: tuple[Fraction, Fraction, Fraction],
    margin: Fraction,
    max_gross: Fraction,
) -> None:
    require(container.recipe.max_gross_kg <= max_gross, "whole place payload")
    require(
        all(
            d + 2 * margin <= bound
            for d, bound in zip(container.recipe.outer, dimensions, strict=True)
        ),
        "whole place dimensions",
    )
