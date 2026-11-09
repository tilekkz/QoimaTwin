"""Replay actual conveyor intervals without another scheduler or guessed poses."""

from dataclasses import replace

from app.v3.belt_geometry import footprint, requirements
from app.v3.belt_models import BeltEvent, BeltMotion
from app.v3.belt_plan import compile_job
from app.v3.belt_state import RunningCarrier, settled_invariants, snapshot
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.coordinator_run_belt_plan import job, parcel, payload, steps
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.light_flow_models import FlowEvent


class BeltJournal:
    def __init__(self, source: ConveyorSource, inventory: InventoryJournal) -> None:
        self.source, self.inventory = source, inventory
        self.states: dict[str, RunningCarrier] = {}
        self.leases: dict[str, str] = {}
        self.external: dict[str, str] = {}
        self.outputs: set[str] = set()
        self.seq = 0

    def apply(self, event: FlowEvent) -> None:
        if event.kind == "operation_started" and event.operation is not None:
            if event.operation.kind == "deposit":
                candidate = job(self.inventory, event.order_id, event.operation.planned_end_tick)
                prepared = steps(
                    self.source, candidate, self.inventory.views[event.order_id].times.clear
                )
                self._reserve(event.order_id, prepared[0].resources)
        elif event.kind == "packing_reserved":
            self._pack_reservation(event.order_id)
        elif event.kind == "output_collected":
            self._collect(event)
        if event.belt_event is not None:
            self._event(event)
        elif event.kind.startswith("belt:"):
            raise ValueError("Native conveyor event lost its exact physical payload")

    def _reserve(self, key: str, resources: frozenset[str]) -> None:
        if any(
            self.leases.get(r, key) != key or self.external.get(r, key) != key for r in resources
        ):
            raise ValueError("Conveyor physical reservation overlaps another job")
        self.external.update((r, key) for r in resources)

    def _pack_reservation(self, key: str) -> None:
        state = self.states.get(key)
        if state is None or state.pose is None or state.active is not None:
            raise ValueError("Packing reservation lacks an actual stationary belt carrier")
        predicted = parcel(self.inventory, key)
        compiled = compile_job(
            self.source, replace(state.job, hu_id=predicted.payload_id, payload=predicted)
        )
        station = next(step for step in compiled if step.phase == "station")
        same(station.end, state.pose, "Packing replacement resets actual source pose")
        resources = requirements(self.source, footprint(self.source, predicted, state.pose))
        resources |= state.steps[state.index].resources | state.steps[state.index + 1].resources
        self._reserve(key, resources)

    def _collect(self, event: FlowEvent) -> None:
        key = event.order_id
        if key not in self.outputs:
            raise ValueError("Parcel collection precedes actual physical output arrival")
        state = self.states[key]
        state.stop_waiting(event.tick)
        state.complete, state.index = True, len(state.steps)
        self.outputs.remove(key)

    def _event(self, outer: FlowEvent) -> None:
        event = outer.belt_event
        if event is None:
            raise ValueError("Missing embedded conveyor event")
        if (event.seq, event.tick, event.job_id, "belt:" + event.kind) != (
            self.seq,
            outer.tick,
            outer.order_id,
            outer.kind,
        ):
            raise ValueError("Conveyor event clock, sequence or physical identity differs")
        self.seq += 1
        if event.kind == "arrived":
            self._arrive(event)
        if event.job_id not in self.states:
            raise ValueError("Conveyor fact precedes actual paid intake handoff")
        state = self.states[event.job_id]
        self._change(state, event)
        self._event_value(state, event)

    def _arrive(self, event: BeltEvent) -> None:
        key = event.job_id
        if key in self.states:
            raise ValueError("Duplicate actual belt carrier")
        candidate = job(self.inventory, key, event.tick)
        if self.inventory.ledger.contents(candidate.hu_id).container.owner_id != "belt:" + key:
            raise ValueError("Belt admission lacks actual stock custody")
        prepared = steps(self.source, candidate, self.inventory.views[key].times.clear)
        if any(self.external.get(r) != key for r in prepared[0].resources):
            raise ValueError("Actual belt intake lost its paid deposit reservation")
        self.states[key] = RunningCarrier(
            candidate, prepared, arrived=True, waiting_since=event.tick
        )
        self.external = {r: owner for r, owner in self.external.items() if owner != key}

    def _change(self, state: RunningCarrier, event: BeltEvent) -> None:
        kind = event.kind
        if kind == "leases_acquired":
            self._acquire(state, event)
        elif kind == "leases_released":
            self._release(state, event)
        elif kind == "admitted":
            if state.admitted:
                raise ValueError("Duplicate physical belt admission")
            state.admitted = True
        elif kind in {"motion_started", "pivot_started", "station_started"}:
            self._start(state, event)
        elif kind in {"motion_completed", "pivot_completed", "station_completed"}:
            self._finish(state, event)
        elif kind in {"contents_changed", "container_replaced"}:
            self._payload(state, event)
        elif kind == "completed":
            if not state.complete or any(v == event.job_id for v in self.leases.values()):
                raise ValueError("Belt completion lacks actual collection and resource release")
        elif kind != "arrived":
            raise ValueError("Unknown native conveyor fact")

    def _acquire(self, state: RunningCarrier, event: BeltEvent) -> None:
        step, key = state.steps[state.index], state.job.job_id
        if any(self.leases.get(r, key) != key for r in step.resources):
            raise ValueError("Conveyor motion overlaps another physical lease")
        acquired = tuple(sorted(step.resources - self.leases.keys()))
        same(
            event.resources, acquired, "Conveyor acquisition differs from compiled swept footprint"
        )
        self.leases.update((r, key) for r in acquired)
        state.pose = step.start

    def _release(self, state: RunningCarrier, event: BeltEvent) -> None:
        keep = frozenset[str]()
        if not state.complete:
            if state.pose is None:
                raise ValueError("Conveyor release has no actual physical pose")
            keep = requirements(self.source, footprint(self.source, state.job.payload, state.pose))
            keep |= state.steps[state.index].guards
        released = tuple(
            sorted(r for r, key in self.leases.items() if key == event.job_id and r not in keep)
        )
        same(event.resources, released, "Conveyor release differs from retained physical footprint")
        for resource in released:
            del self.leases[resource]

    def _start(self, state: RunningCarrier, event: BeltEvent) -> None:
        step = state.steps[state.index]
        if state.active is not None or state.complete or event.job_id in self.outputs:
            raise ValueError("Conveyor operation overlaps or starts after completion")
        if event.kind != step.phase + "_started":
            raise ValueError("Conveyor stage differs from compiled source route")
        if any(self.leases.get(r) != event.job_id for r in step.resources):
            raise ValueError("Conveyor start lacks its compiled swept reservations")
        if event.planned_end_tick != event.tick + step.duration_tick:
            raise ValueError("Conveyor duration differs from compiled source motion")
        state.pose = step.start
        state.stop_waiting(event.tick)
        state.active = BeltMotion(
            step.phase, event.tick, event.tick + step.duration_tick, step.start, step.end
        )

    def _finish(self, state: RunningCarrier, event: BeltEvent) -> None:
        motion = state.active
        if motion is None or motion.planned_end_tick != event.tick:
            raise ValueError("Conveyor completion has no actual observed end")
        if event.kind != motion.phase + "_completed":
            raise ValueError("Conveyor completion changes its physical stage")
        state.pose, state.active, state.waiting_since = motion.end, None, event.tick
        if state.index == len(state.steps) - 1:
            self.outputs.add(event.job_id)
        else:
            state.index += 1

    def _payload(self, state: RunningCarrier, event: BeltEvent) -> None:
        key, order = event.job_id, self.inventory.units[event.job_id]
        identity = order.carrier_id if event.kind == "contents_changed" else order.package_id
        kind = "order_tote" if event.kind == "contents_changed" else "sealed_parcel"
        updated = payload(self.inventory, key, identity, kind)
        if event.kind == "contents_changed":
            state.job = replace(state.job, payload=updated)
            return
        candidate = replace(state.job, hu_id=identity, payload=updated)
        compiled = compile_job(self.source, candidate)
        index = next(i for i, step in enumerate(compiled) if step.phase == "station")
        same(state.pose, compiled[index].end, "Parcel replacement changes actual station pose")
        self.leases.update((r, key) for r, owner in self.external.items() if owner == key)
        self.external = {r: owner for r, owner in self.external.items() if owner != key}
        state.job = candidate
        state.steps = (*state.steps[: state.index + 1], *compiled[index + 1 :])

    def _event_value(self, state: RunningCarrier, event: BeltEvent) -> None:
        expected = (
            state.job.hu_id,
            state.job.payload.payload_id,
            state.pose.edge_id if state.pose else None,
            state.pose,
            state.active.planned_end_tick if state.active else None,
        )
        same(
            (event.hu_id, event.payload_id, event.edge_id, event.pose, event.planned_end_tick),
            expected,
            "Conveyor event differs from actual physical state",
        )
        if event.kind not in {"leases_acquired", "leases_released"}:
            held = tuple(sorted(r for r, key in self.leases.items() if key == event.job_id))
            same(event.resources, held, "Conveyor event lost actual held resources")

    def check(self, point: CoordinatorSnapshot) -> None:
        values = tuple(self.states.values())
        settled_invariants(self.source, values, self.leases, point.tick)
        same(
            point.belt,
            snapshot(self.source, values, self.leases, point.tick),
            "Captured conveyor differs from actual source motion journal",
        )
