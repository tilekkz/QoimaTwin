"""Current unit-job progress from completed operations; no duplicate physical actor state."""

from dataclasses import dataclass

from app.v3.light_flow_state import HumanStep


@dataclass(frozen=True, slots=True)
class UnitProgress:
    order_id: str
    completed_picker_steps: int
    picked_tick: int | None
    deposited_tick: int | None
    collected_tick: int | None
    cart_released_tick: int | None
    picker_returned_tick: int | None
    completed_shipper_steps: int
    shipper_returned_tick: int | None


@dataclass
class UnitState:
    order_id: str
    picker_steps: tuple[HumanStep, ...]
    completed_picker_steps: int = 0
    picked_tick: int | None = None
    deposited_tick: int | None = None
    collected_tick: int | None = None
    cart_released_tick: int | None = None
    picker_returned_tick: int | None = None
    shipper_steps: tuple[HumanStep, ...] = ()
    completed_shipper_steps: int = 0
    shipper_returned_tick: int | None = None

    def view(self) -> UnitProgress:
        return UnitProgress(
            self.order_id,
            self.completed_picker_steps,
            self.picked_tick,
            self.deposited_tick,
            self.collected_tick,
            self.cart_released_tick,
            self.picker_returned_tick,
            self.completed_shipper_steps,
            self.shipper_returned_tick,
        )
