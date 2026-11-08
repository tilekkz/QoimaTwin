"""Per-order physical bindings and actual finite packing ownership, without worker copies."""

from dataclasses import dataclass

from app.v3.conveyor_models import ConveyorPayload


@dataclass(frozen=True, slots=True)
class UnitContext:
    order_id: str
    picker_id: str
    cart_id: str
    station_id: str
    shipper_id: str
    source_node: str
    intake_node: str
    output_node: str
    port_id: str


@dataclass(frozen=True, slots=True)
class PackingView:
    order_id: str
    actor_id: str
    station_id: str
    role_intent_id: str | None
    phase: str
    assigned_tick: int
    packed_tick: int | None
    cleared_tick: int | None
    released_tick: int | None
    held_resources: tuple[str, ...]


@dataclass
class PackingState:
    order_id: str
    actor_id: str
    station_id: str
    role_intent_id: str | None
    assigned_tick: int
    parcel: ConveyorPayload
    belt_resources: frozenset[str]
    engine_resources: tuple[str, ...]
    assigned_node: str
    phase: str = "approach"
    packed_tick: int | None = None
    cleared_tick: int | None = None
    released_tick: int | None = None

    def held_resources(self) -> tuple[str, ...]:
        if self.phase == "complete":
            return ()
        if self.phase == "returning":
            return self.engine_resources[:1]
        return self.engine_resources

    def view(self) -> PackingView:
        return PackingView(
            self.order_id,
            self.actor_id,
            self.station_id,
            self.role_intent_id,
            self.phase,
            self.assigned_tick,
            self.packed_tick,
            self.cleared_tick,
            self.released_tick,
            self.held_resources(),
        )
