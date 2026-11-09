"""Local PALLET operations share the existing heap, HumanState and StockLedger."""

import heapq
from collections.abc import Callable
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_wire import record
from app.v3.light_flow_models import FlowSnapshot
from app.v3.light_flow_state import HumanState, HumanStep
from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_proof import validate_proof
from app.v3.pallet_shared_authority import binding_bytes, check_authority, type_bytes
from app.v3.pallet_shared_inputs import validate_inputs
from app.v3.pallet_shared_invariants import check_shared
from app.v3.pallet_shared_models import (
    PalletSharedEvent,
    PalletSharedOutcome,
    PalletSharedProfile,
    PalletSharedSnapshot,
)
from app.v3.pallet_shared_observe import snapshot, vehicle_view
from app.v3.pallet_shared_plan import resource_ids, shared_plan
from app.v3.pallet_shared_state import PalletJobState, PalletVehicleState
from app.v3.stock_claims import StockClaim
from app.v3.stock_models import StockDelta
from app.v3.whole_flow_engine import WholeFlowEngine


def native(value: FlowSnapshot) -> PalletSharedSnapshot:
    if not isinstance(value, PalletSharedSnapshot):
        raise RuntimeError("Shared PALLET requires its distinct native snapshot")
    return value


class PalletSharedEngine(WholeFlowEngine):
    def __init__(
        self,
        profile: PalletSharedProfile,
        conveyor: ConveyorSource,
        proof_root: Path,
        proof: LocalGeometryProof,
        *,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None = None,
    ) -> None:
        validate_inputs(profile, proof)
        self.pallet_profile = profile
        self.binding_bytes = binding_bytes(profile)
        self.world_bytes = canonical_bytes(record(profile.world))
        self.world_type_bytes = type_bytes(profile.world)
        self.profile_sha256 = sha256(canonical_bytes(record(profile))).hexdigest()
        self.proof = validate_proof(proof_root, proof)
        self.plan, self.bridge = shared_plan(profile, proof_root)
        self.proof_bytes = canonical_bytes(asdict(self.proof))
        self.plan_bytes = canonical_bytes(record(self.plan))
        self.pallet_jobs = {
            j.job_id: PalletJobState(j)
            for j in sorted(profile.jobs, key=lambda j: (j.ready_tick, j.job_id))
        }
        self.vehicle = PalletVehicleState(self.plan[0].start_pose)
        self.pallet_resources = resource_ids(profile, self.bridge)
        self.resource_bytes = canonical_bytes(record(self.pallet_resources))
        self.bridge_bytes = canonical_bytes(record(self.bridge))
        super().__init__(profile.world, conveyor, on_tick_settled=on_tick_settled)
        self.token_bytes = canonical_bytes(
            record(tuple(u.token for u in self.ledger.contents(profile.hu_id).units))
        )
        self._check()

    def run(self, horizon_tick: int, end_tick: int) -> PalletSharedOutcome:
        check_authority(self)
        if type(horizon_tick) is not int or any(
            j.spec.ready_tick >= horizon_tick for j in self.pallet_jobs.values()
        ):
            raise ValueError("Every shared local PALLET offer must arrive strictly before H")
        result = super().run(horizon_tick, end_tick)
        return PalletSharedOutcome(
            result.status,
            result.events,
            native(result.at_horizon),
            native(result.at_end),
            tuple(native(s) for s in result.checkpoints),
            self.bridge,
            geometry_proof=self.proof,
            profile_sha256=self.profile_sha256,
            requested_end_tick_limit=end_tick,
        )

    def _initial_calendar(self) -> None:
        super()._initial_calendar()
        for key, state in self.pallet_jobs.items():
            heapq.heappush(self.pending, (state.spec.ready_tick, "pallet_arrival", key))

    def _calendar_event(self, kind: str, key: str) -> None:
        if kind == "pallet_arrival":
            self.pallet_jobs[key].status = "waiting"
            self._emit("pallet_arrived", key)
        else:
            super()._calendar_event(kind, key)

    def _dispatch_external(self) -> None:
        super()._dispatch_external()
        worker = self.workers["F01"]
        if self.tick >= self.horizon or worker.order_id is not None:
            return
        if worker.spec.available_tick > self.tick or self.vehicle.job_id is not None:
            return
        waiting = [s for s in self.pallet_jobs.values() if s.status == "waiting"]
        if waiting:
            self._admit_pallet(min(waiting, key=lambda s: (s.spec.ready_tick, s.spec.job_id)))

    def _admit_pallet(self, state: PalletJobState) -> None:
        p, worker = self.pallet_profile, self.workers["F01"]
        if any(r in self.leases for r in self.pallet_resources):
            state.wait_reason = "resources"
            return
        if any(c.container_id == p.hu_id for c in self.ledger.claims):
            state.wait_reason = "inventory_claim"
            return
        if self.ledger.contents(p.hu_id).container.owner_id != p.platform_id:
            state.wait_reason = "platform_custody"
            return
        key = state.spec.job_id
        claim = self.ledger.reserve_hu("pallet:" + key, key, self.ledger.revision, p.hu_id)
        self.leases.update((resource, key) for resource in self.pallet_resources)
        self.vehicle.job_id = key
        state.admitted_tick, state.status, state.wait_reason = self.tick, "active", None
        worker.order_id, worker.task = key, "pallet_cycle"
        worker.steps = [
            HumanStep(f"pallet:{op.ordinal}:{op.kind}", p.driver_anchor, op.duration_ticks)
            for op in self.plan
        ]
        worker.waiting_since = self.tick
        self._pallet_event("inventory_claim_acquired", key, claim=claim)
        for resource in self.pallet_resources:
            self._pallet_event("pallet_resource_acquired", key, resource=resource)
        self._emit("pallet_cycle_started", key, worker=worker)

    def _human_effect(self, order_id: str, kind: str) -> None:
        if order_id not in self.pallet_jobs:
            super()._human_effect(order_id, kind)
            return
        state, p = self.pallet_jobs[order_id], self.pallet_profile
        op = self.plan[state.completed_steps]
        if kind != f"pallet:{op.ordinal}:{op.kind}":
            raise RuntimeError("PALLET completion differs from the proved paid plan")
        self.vehicle.pose = op.end_pose
        state.completed_steps += 1
        if op.kind in {"attach", "release"}:
            owner = p.vehicle_owner_id if op.kind == "attach" else p.platform_id
            delta = self.ledger.transfer_whole_hu(
                order_id + ":" + op.kind,
                self.ledger.revision,
                p.hu_id,
                owner,
                claim_id="pallet:" + order_id,
            )
            if op.kind == "attach":
                state.attached_tick = self.tick
            else:
                state.released_tick = self.tick
            self._emit("pallet_" + op.kind + "_completed", order_id, delta=delta)

    def _task_finished(self, worker: HumanState) -> None:
        if worker.task != "pallet_cycle" or worker.steps:
            super()._task_finished(worker)
            return
        key = worker.order_id
        if key is None:
            raise RuntimeError("PALLET driver has no admitted job")
        state = self.pallet_jobs[key]
        self.ledger.release_claim("pallet:" + key, key)
        self._pallet_event("inventory_claim_released", key, released="pallet:" + key)
        for resource in self.pallet_resources:
            if self.leases.pop(resource, None) != key:
                raise RuntimeError("PALLET safe return lost a required reservation")
            self._pallet_event("pallet_resource_released", key, resource=resource)
        state.completed_tick, state.status = self.tick, "complete"
        self.vehicle.job_id = None
        super()._task_finished(worker)
        self._emit("pallet_cycle_completed", key, worker=worker)

    def _place_free(self, owner_id: str) -> bool:
        return "slot:" + owner_id not in self.leases and super()._place_free(owner_id)

    def _additional_whole_ownership(self) -> tuple[dict[str, str], frozenset[str]]:
        return check_shared(self)

    def _complete(self) -> bool:
        return super()._complete() and all(
            s.status == "complete" for s in self.pallet_jobs.values()
        )

    def _observe(self, tick: int) -> PalletSharedSnapshot:
        return snapshot(self, super()._observe(tick))

    def _emit(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
    ) -> None:
        if order_id in self.pallet_jobs:
            self._pallet_event(kind, order_id, worker=worker, delta=delta)
        else:
            super()._emit(kind, order_id, worker=worker, delta=delta)

    def _pallet_event(
        self,
        kind: str,
        key: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
        claim: StockClaim | None = None,
        released: str | None = None,
        resource: str | None = None,
    ) -> None:
        self.events.append(
            PalletSharedEvent(
                len(self.events),
                self.tick,
                kind,
                key,
                actor_id="F01",
                operation=worker.operation if worker else None,
                delta=delta,
                inventory_claim=claim,
                released_claim_id=released,
                resource_id=resource,
                pallet_job=self.pallet_jobs[key].view(),
                vehicle=vehicle_view(self, self.tick),
            )
        )
