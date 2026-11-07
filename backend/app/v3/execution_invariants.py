"""Authoritative settled-tick accounting and resource assertions for the manual slice."""

from collections import Counter

from app.v3.execution_state import ManualState
from app.v3.execution_types import HUOwner


def _fail(message: str) -> None:
    raise RuntimeError(f"manual invariant: {message}")


def _owners(state: ManualState) -> None:
    if state.owners.keys() != {hu.hu_id for hu in state.profile.handling_units}:
        _fail("HU ownership universe changed")
    places: set[tuple[str, str]] = set()
    locations = _locations(state)
    for hu_id, owner in state.owners.items():
        if owner.hu_id != hu_id:
            _fail("HU owner key mismatch")
        if owner.kind not in locations or owner.location_id not in locations[owner.kind]:
            _fail("unknown HU owner kind or place")
        if owner.kind in {"stock", "buffer", "worker", "service"}:
            key = owner.kind, owner.location_id
            if key in places:
                _fail("multiple HUs occupy one exclusive place or worker")
            places.add(key)


def _locations(state: ManualState) -> dict[str, set[str]]:
    ports = {p.port_id for p in state.profile.ports}
    return {
        "unreleased": {"outside"},
        "outside": {"outside"},
        "stock": {s.place_id for s in state.profile.slots},
        "buffer": {b.place_id for p in state.profile.ports for b in p.buffer_places},
        "worker": {a.actor_id for a in state.profile.actors},
        "service": ports,
        "shipped": ports,
    }


def _resource_universe(state: ManualState) -> set[str]:
    locations = _locations(state)
    groups = (
        ("worker", locations["worker"]),
        ("buffer", locations["buffer"]),
        ("port", locations["service"]),
        ("slot", locations["stock"]),
        ("hu", {h.hu_id for h in state.profile.handling_units}),
    )
    return {f"{kind}:{value}" for kind, values in groups for value in values}


def _quantities(state: ManualState) -> None:
    initial = {p.hu_id for p in state.profile.initial_placements}
    expected: Counter[str] = Counter()
    warehouse: Counter[str] = Counter()
    for hu in state.profile.handling_units:
        if hu.hu_id in initial | state.arrived:
            expected[hu.sku_id] += hu.quantity
        if hu.hu_id in initial | state.admitted:
            warehouse[hu.sku_id] += hu.quantity
    physical = dict(state.units({"outside", "stock", "buffer", "worker", "service", "shipped"}))
    inside = dict(state.units({"stock", "buffer", "worker", "service", "shipped"}))
    if expected != physical or warehouse != inside:
        _fail("per-SKU conservation failed")


def _owner_lease(state: ManualState, owner: HUOwner) -> None:
    if owner.kind == "buffer" and f"buffer:{owner.location_id}" not in state.leases:
        _fail("occupied buffer has no exclusive lease")
    if owner.kind == "worker" and f"worker:{owner.location_id}" not in state.leases:
        _fail("carrying actor has no exclusive lease")
    if owner.kind == "service" and f"port:{owner.location_id}" not in state.leases:
        _fail("HU service has no exclusive bay")


def check_manual_invariants(state: ManualState) -> None:
    _owners(state)
    _quantities(state)
    universe = _resource_universe(state)
    for resource, lease in state.leases.items():
        if (
            resource not in universe
            or resource != lease.resource_id
            or lease.job_id not in state.jobs
        ):
            _fail("invalid resource lease")
    for actor_id, worker in state.workers.items():
        worker_lease = state.leases.get(f"worker:{actor_id}")
        if (worker_lease.job_id if worker_lease else None) != worker.job_id:
            _fail("worker has conflicting job and resource ownership")
        if (worker.node_id is None) == (worker.motion is None):
            _fail("worker position must be a node or one active motion")
        if worker.motion is not None and worker.motion.end_tick < worker.motion.start_tick:
            _fail("worker motion runs backwards")
    for owner in state.owners.values():
        _owner_lease(state, owner)
