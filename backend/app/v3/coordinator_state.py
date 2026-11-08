"""Role metadata only: actual worker position/operations remain in the inherited worker map."""

from dataclasses import dataclass

from app.v3.coordinator_models import RoleIntent, RoleView


@dataclass
class RoleState:
    intent: RoleIntent
    status: str = "unreleased"
    departed_tick: int | None = None
    activated_tick: int | None = None
    return_started_tick: int | None = None
    restored_tick: int | None = None
    reason: str | None = None

    def view(self) -> RoleView:
        return RoleView(
            self.intent.intent_id,
            self.intent.actor_id,
            self.intent.station_id,
            self.status,
            self.departed_tick,
            self.activated_tick,
            self.return_started_tick,
            self.restored_tick,
            self.reason,
        )
