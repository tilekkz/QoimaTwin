"""C journal commands derive destinations and placements from immutable choices."""

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units import order_views
from app.v3.light_flow_models import FlowEvent, FlowProfile
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockDelta


class StockCommands:
    def __init__(self, profile: CoordinatorProfile) -> None:
        self.profile = profile
        flow = profile.world.receipts.flow
        self.ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
        self.units = {o.order_id: o for o in flow.orders}
        self.views = order_views(profile) or {key: flow for key in self.units}
        self.receipts = {o.definition.receipt_id: o for o in profile.world.receipts.receipts}
        self.whole = {o.job_id: o for o in profile.world.orders}
        self.receipt_ports = {p.port_id: p for p in profile.world.receipts.ports}
        self.whole_ports = {p.port_id: p for p in profile.world.ports}

    def unit_delta(self, event: FlowEvent) -> StockDelta:
        order, view = self.units[event.order_id], self.views[event.order_id]
        tx, revision = event.order_id + ":", self.ledger.revision
        if event.kind == "picked":
            return self.ledger.pick(
                tx + "pick",
                revision,
                order.source_hu,
                order.carrier_id,
                order.carrier_placements,
                claim_id="pick:" + order.order_id,
            )
        if event.kind == "packed":
            return self.ledger.pack(
                tx + "pack",
                revision,
                order.carrier_id,
                order.package_id,
                order.package_placements,
                order_id=order.order_id,
            )
        if event.kind == "shipped":
            return self.ledger.ship(tx + "ship", revision, order.package_id, view.shipped_owner)
        material, owner = self._material(event, view)
        operation = (
            self.ledger.transfer_material_to_worker
            if owner.startswith("actor:")
            else (self.ledger.relocate)
        )
        return operation(tx + event.kind, revision, material, owner)

    def _material(self, event: FlowEvent, view: FlowProfile) -> tuple[str, str]:
        order = self.units[event.order_id]
        values = {
            "carrier_attached": (order.carrier_id, view.cart.owner_id),
            "carrier_reattached": (order.carrier_id, view.cart.owner_id),
            "carrier_detached": (order.carrier_id, "actor:" + view.picker_id),
            "source_carrier_detached": (order.carrier_id, "actor:" + view.picker_id),
            "intake_handoff": (order.carrier_id, "belt:" + order.order_id),
            "package_prepared": (order.package_id, view.station.bench_owner),
            "empty_carrier_cleared": (order.carrier_id, view.station.empty_owner),
            "parcel_loaded": (order.package_id, "belt:" + order.order_id),
            "output_collected": (order.package_id, "actor:" + view.shipper_id),
        }
        if event.kind not in values:
            raise ValueError("Unknown unit stock delta kind")
        return values[event.kind]

    def receipt_delta(self, event: FlowEvent, actor: str, buffer: str) -> StockDelta:
        offer, key = self.receipts[event.order_id], event.order_id
        tx, rev, hu = key + ":", self.ledger.revision, offer.definition.hu_id
        if event.kind == "receipt_credited":
            return self.ledger.receive_hu(tx + "receive", rev, offer.definition, "actor:" + actor)
        owners = {
            "receipt_buffered": buffer,
            "receipt_buffer_picked": "actor:" + actor,
            "receipt_putaway": offer.slot_owner_id,
        }
        if event.kind not in owners:
            raise ValueError("Unknown receipt stock delta kind")
        return self.ledger.transfer_whole_hu(
            tx + event.kind, rev, hu, owners[event.kind], claim_id="receipt:" + key
        )

    def whole_delta(self, event: FlowEvent, actor: str, buffer: str) -> StockDelta:
        order, key = self.whole[event.order_id], event.order_id
        tx, rev = key + ":", self.ledger.revision
        if event.kind == "whole_shipped":
            port = self.whole_ports[order.port_id]
            return self.ledger.ship_whole_hu(
                tx + "ship", rev, order.hu_id, port.shipped_owner, claim_id="whole:" + key
            )
        owners = {
            "whole_picked": "actor:" + actor,
            "whole_buffered": buffer,
            "whole_buffer_picked": "actor:" + actor,
        }
        if event.kind not in owners:
            raise ValueError("Unknown whole stock delta kind")
        return self.ledger.transfer_whole_hu(
            tx + event.kind, rev, order.hu_id, owners[event.kind], claim_id="whole:" + key
        )
