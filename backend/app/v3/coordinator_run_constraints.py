"""Staff violations are observed facts, not a caller-selectable final status label."""

from collections import Counter

from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, StaffViolation
from app.v3.coordinator_run_inventory import InventoryJournal
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_resources import ResourceJournal
from app.v3.coordinator_run_role_exposure import available
from app.v3.coordinator_run_roles import RoleJournal
from app.v3.light_flow_models import FlowEvent


class ConstraintJournal:
    def __init__(self, profile: CoordinatorProfile) -> None:
        self.profile = profile
        self.violations: set[StaffViolation] = set()
        self.rejected: dict[str, int] = {}
        self.availability: Counter[tuple[str, int]] = Counter()

    def apply(
        self,
        event: FlowEvent,
        motion: MotionJournal,
        inventory: InventoryJournal,
        resources: ResourceJournal,
    ) -> None:
        if event.kind == "role_rejected":
            intent = next(i for i in self.profile.intents if i.intent_id == event.order_id)
            self.rejected[event.order_id] = event.tick
            self.violations.add(
                StaffViolation(event.tick, intent.actor_id, "ROLE_WINDOW_TOO_SHORT", event.order_id)
            )
        if event.kind != "availability_changed":
            return
        actor = event.actor_id
        if actor not in motion.workers or event.order_id != "availability:" + str(actor):
            raise ValueError("Availability event lost its actual worker identity")
        declared = {
            (w.actor_id, t)
            for w in self.profile.registry.unavailability
            for t in (w.start_tick, w.end_tick)
        }
        key = (actor, event.tick)
        if key not in declared:
            raise ValueError("Availability fact is not one exact declared boundary")
        self.availability[key] += 1
        if not available(self.profile, actor, event.tick) and not self._clean(
            actor, motion, inventory, resources
        ):
            self.violations.add(StaffViolation(event.tick, actor, "PRIMARY_BREAK_NOT_CLEAN"))

    @staticmethod
    def _clean(
        actor: str, motion: MotionJournal, inventory: InventoryJournal, resources: ResourceJournal
    ) -> bool:
        worker = motion.workers[actor]
        if (
            worker.order_id is not None
            or worker.operation is not None
            or worker.waiting_since is not None
        ):
            return False
        if any(c.owner_id == "actor:" + actor for c in inventory.ledger.snapshot().containers):
            return False
        if any(r in resources.leases for r in ("receipt:worker:" + actor, "whole:worker:" + actor)):
            return False
        return not any(
            inventory.views[key].picker_id == actor for key in motion.cart_orders.values()
        )

    def check(self, outcome: CoordinatorOutcome, roles: RoleJournal) -> None:
        end = outcome.at_end.tick
        expected_boundaries = Counter(
            (w.actor_id, t)
            for w in self.profile.registry.unavailability
            for t in (w.start_tick, w.end_tick)
            if t <= end
        )
        if self.availability != expected_boundaries:
            raise ValueError("Staffing history lost a declared availability boundary")
        for intent in self.profile.intents:
            if intent.restore_by_tick > end:
                continue
            view = roles.views[intent.intent_id]
            rejected = self.rejected.get(intent.intent_id)
            if (view.restored_tick is None or view.restored_tick > intent.restore_by_tick) and (
                rejected is None or rejected >= intent.restore_by_tick
            ):
                self.violations.add(
                    StaffViolation(
                        intent.restore_by_tick,
                        intent.actor_id,
                        "RESTORATION_DEADLINE_MISSED",
                        intent.intent_id,
                    )
                )
        if len(set(outcome.constraint_violations)) != len(outcome.constraint_violations):
            raise ValueError("Duplicate native staffing violation")
        if set(outcome.constraint_violations) != self.violations:
            raise ValueError(
                "Native staffing violations differ from actual calendar and role facts"
            )
