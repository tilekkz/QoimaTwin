"""Physical whole-job stage facts; all material ownership stays in StockLedger."""

from dataclasses import dataclass

from app.v3.whole_flow_models import WholeHUOrder, WholeHUView


def exposure(start: int | None, end: int | None, now: int) -> int:
    return 0 if start is None else (now if end is None else min(now, end)) - start


@dataclass
class WholeState:
    spec: WholeHUOrder
    status: str = "unreleased"
    actor_id: str | None = None
    buffer_owner_id: str | None = None
    admitted_tick: int | None = None
    picked_tick: int | None = None
    buffered_tick: int | None = None
    buffer_picked_tick: int | None = None
    port_reserved_tick: int | None = None
    service_started_tick: int | None = None
    shipped_tick: int | None = None
    returned_tick: int | None = None
    wait_reason: str | None = None
    ready_tick: int | None = None

    def view(self, tick: int) -> WholeHUView:
        return WholeHUView(
            self.spec.job_id,
            self.status,
            self.actor_id,
            self.buffer_owner_id,
            self.admitted_tick,
            self.picked_tick,
            self.buffered_tick,
            self.buffer_picked_tick,
            self.port_reserved_tick,
            self.service_started_tick,
            self.shipped_tick,
            self.returned_tick,
            self.wait_reason,
            exposure(self.admitted_tick, self.returned_tick, tick),
            exposure(self.port_reserved_tick, self.shipped_tick, tick),
            exposure(self.service_started_tick, self.shipped_tick, tick),
        )
