"""Role state changes require declared intent clocks and actual physical paid arrivals."""

from collections.abc import Mapping
from dataclasses import replace
from urllib.parse import quote

from app.v3.coordinator_models import (
    CoordinatorEvent,
    CoordinatorProfile,
    CoordinatorSnapshot,
    RoleView,
)
from app.v3.coordinator_run_inventory import same
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_role_exposure import actor_roles, available, exposure
from app.v3.coordinator_validation import role_route
from app.v3.light_flow_models import FlowEvent


class RoleJournal:
    def __init__(self, profile: CoordinatorProfile, motion: MotionJournal) -> None:
        self.profile, self.motion = profile, motion
        self.intents = {i.intent_id: i for i in profile.intents}
        self.views = {
            i.intent_id: RoleView(
                i.intent_id, i.actor_id, i.station_id, "unreleased", None, None, None, None, None
            )
            for i in profile.intents
        }

    def before(self, event: FlowEvent, leases: Mapping[str, str]) -> None:
        if event.kind != "role_transition_assigned":
            return
        if event.order_id not in self.intents:
            raise ValueError("Role assignment has no declared intent")
        intent, old = self.intents[event.order_id], self.views[event.order_id]
        if not self._clean(intent.actor_id, leases):
            raise ValueError("Role assignment requires actual clean helper custody")
        if old.status != "quiescing":
            return
        station = next(s for s in self.profile.stations if s.station_id == intent.station_id)
        primary = next(
            s.primary_actor_id
            for s in self.profile.registry.station_bindings
            if s.station_id == intent.station_id
        )
        if available(self.profile, primary, event.tick) or not self._clean(primary, leases):
            raise ValueError("Role station requires a clean unavailable primary actor")
        if "staff:station:" + station.station_id in self.leases():
            raise ValueError("Role station already has an actual helper assignment")
        if "pack:bench:" + quote(station.bench_owner, safe="") in leases:
            raise ValueError("Role station bench has an active goods reservation")
        if any(
            c.owner_id == station.bench_owner
            for c in self.motion.inventory.ledger.snapshot().containers
        ):
            raise ValueError("Role station bench is physically occupied")

    def _clean(self, actor: str, leases: Mapping[str, str]) -> bool:
        worker = self.motion.workers[actor]
        if (
            worker.order_id is not None
            or worker.operation is not None
            or worker.steps
            or worker.waiting_since is not None
        ):
            return False
        if any(
            c.owner_id == "actor:" + actor
            for c in self.motion.inventory.ledger.snapshot().containers
        ):
            return False
        if any(
            prefix + actor in leases
            for prefix in ("receipt:worker:", "whole:worker:", "pack:worker:")
        ):
            return False
        return not any(
            self.motion.inventory.views[job].picker_id == actor
            for job in self.motion.cart_orders.values()
        )

    def apply(self, event: FlowEvent) -> None:
        if event.order_id not in self.intents:
            if isinstance(event, CoordinatorEvent) and event.role_view is not None:
                raise ValueError("Unknown role event identity")
            return
        if not isinstance(event, CoordinatorEvent) or event.role_view is None:
            raise ValueError("Role event lost its exact native role view")
        if event.actor_id != self.intents[event.order_id].actor_id:
            raise ValueError("Role event changed its declared physical actor")
        expected = self._transition(event)
        same(event.role_view, expected, "Native role view differs from actual transition")
        self.views[event.order_id] = expected

    def _transition(self, event: CoordinatorEvent) -> RoleView:
        old, intent = self.views[event.order_id], self.intents[event.order_id]
        kind, tick = event.kind, event.tick
        if kind == "role_requested":
            if old.status != "unreleased" or tick != intent.request_tick:
                raise ValueError("Role request differs from its declared clock")
            return replace(old, status="quiescing")
        if kind == "role_transition_assigned":
            if old.status == "quiescing":
                if not intent.request_tick <= tick <= intent.return_tick:
                    raise ValueError("Role outward admission violates intent window")
                return replace(old, status="outward", departed_tick=tick)
            if old.status not in {"active", "return_wait"} or tick < intent.return_tick:
                raise ValueError("Role return lacks active assignment or declared return time")
            return replace(old, status="returning", return_started_tick=tick)
        if kind in {"role_activated", "role_restored"}:
            return self._arrived(event, old)
        if kind == "role_return_waiting":
            if old.status != "active" or tick < intent.return_tick:
                raise ValueError("Role return wait has no actual active assignment")
            return replace(old, status="return_wait")
        if kind == "role_rejected":
            return self._rejected(event, old)
        if kind not in {"operation_started", "operation_completed"}:
            raise ValueError("Unknown role transition event")
        return old

    def _arrived(self, event: CoordinatorEvent, old: RoleView) -> RoleView:
        outward = event.kind == "role_activated"
        expected_phase, operation = (
            ("outward", "role_outward") if outward else ("returning", "role_return")
        )
        if old.status != expected_phase:
            raise ValueError("Role arrival has no preceding physical transition")
        intent = self.intents[event.order_id]
        node = next(s.node_id for s in self.profile.stations if s.station_id == intent.station_id)
        source, target = (intent.restore_node, node) if outward else (node, intent.restore_node)
        duration, _ = role_route(self.profile, intent.actor_id, source, target)
        started = old.departed_tick if outward else old.return_started_tick
        if started is None or event.tick != started + duration:
            raise ValueError("Role arrival does not complete its declared paid distance")
        if (
            duration
            and (event.order_id, operation, event.tick, intent.actor_id)
            not in self.motion.completed
        ):
            raise ValueError("Role arrival lacks actual operation completion")
        if self.motion.workers[intent.actor_id].node != target:
            raise ValueError("Role arrival lacks actual physical station or restored home")
        return (
            replace(old, status="active", activated_tick=event.tick)
            if outward
            else replace(old, status="restored", restored_tick=event.tick)
        )

    def _rejected(self, event: CoordinatorEvent, old: RoleView) -> RoleView:
        intent = self.intents[event.order_id]
        node = next(s.node_id for s in self.profile.stations if s.station_id == intent.station_id)
        outward, _ = role_route(self.profile, intent.actor_id, intent.restore_node, node)
        returning, _ = role_route(self.profile, intent.actor_id, node, intent.restore_node)
        feasible = (
            event.tick + outward <= intent.return_tick
            and intent.return_tick + returning <= intent.restore_by_tick
        )
        if old.status != "quiescing" or feasible:
            raise ValueError("Role rejection has no actual insufficient restoration window")
        return replace(old, status="rejected", reason="ROLE_WINDOW_TOO_SHORT")

    def leases(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, view in self.views.items():
            resources = []
            if view.status in {"outward", "active", "return_wait", "returning"}:
                resources.append("staff:actor:" + view.actor_id)
            if view.status in {"outward", "active", "return_wait"}:
                resources.append("staff:station:" + view.station_id)
            for resource in resources:
                if resource in result:
                    raise ValueError("Role resource has simultaneous owners")
                result[resource] = key
        return result

    def check(self, state: CoordinatorSnapshot) -> None:
        rows = tuple(self.views[key] for key in sorted(self.views))
        if any(
            self.intents[r.intent_id].request_tick <= state.tick and r.status == "unreleased"
            for r in rows
        ):
            raise ValueError("Declared role request is absent from observed calendar history")
        same(state.roles, rows, "Captured role views differ from actual role journal")
        same(state.actor_roles, actor_roles(self.profile, rows, state.tick), "Actor role differs")
        same(state.exposure, exposure(self.profile, rows, state.tick), "Role exposure differs")
        bindings = tuple(
            sorted(
                (r.station_id, r.actor_id)
                for r in rows
                if r.status in {"outward", "active", "return_wait"}
            )
        )
        same(state.role_bindings, bindings, "Actual role station bindings differ")
        actual = {key: value for key, value in state.leases if key.startswith("staff:")}
        same(actual, self.leases(), "Captured role resource ownership differs")
