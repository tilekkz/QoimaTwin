"""Whole-HU physical custody and reservations must follow completed operations exactly."""

from collections.abc import Mapping
from urllib.parse import quote

from app.v3.light_flow_state import HumanState
from app.v3.receipt_flow_invariants import _receiver_operation
from app.v3.stock_ledger import StockLedger
from app.v3.whole_flow_models import WholeHUPort
from app.v3.whole_flow_state import WholeState


def shipped_resource(port: WholeHUPort, job_id: str) -> str:
    return "whole:shipped:" + quote(port.shipped_owner, safe="") + ":" + quote(job_id, safe="")


def whole_owner(state: WholeState, source: str, port: WholeHUPort) -> str:
    if state.shipped_tick is not None:
        return port.shipped_owner
    if state.buffered_tick is not None and state.buffer_picked_tick is None:
        return str(state.buffer_owner_id)
    if state.picked_tick is not None:
        return "actor:" + str(state.actor_id)
    return source


def whole_resources(state: WholeState, port: WholeHUPort) -> tuple[str, ...]:
    if state.admitted_tick is None or state.returned_tick is not None:
        return ()
    resources = ["whole:worker:" + str(state.actor_id)]
    if state.shipped_tick is None:
        resources.append("whole:hu:" + state.spec.hu_id)
    if state.buffer_picked_tick is None:
        resources.append("whole:place:" + str(state.buffer_owner_id))
    if state.port_reserved_tick is not None and state.shipped_tick is None:
        resources.extend(
            (
                "port:" + port.port_id,
                shipped_resource(port, state.spec.job_id),
            )
        )
    return tuple(resources)


def check_whole_world(
    states: Mapping[str, WholeState],
    ports: Mapping[str, WholeHUPort],
    sources: Mapping[str, str],
    workers: Mapping[str, HumanState],
    leases: Mapping[str, str],
    ledger: StockLedger,
    tick: int,
    receiving: frozenset[str],
) -> tuple[dict[str, str], frozenset[str]]:
    owners, resources, required_claims = {}, {}, set[str]()
    containers = {c.container_id: c for c in ledger.snapshot().containers}
    for key, state in states.items():
        port = ports[state.spec.port_id]
        if state.spec.hu_id in containers and state.spec.hu_id not in receiving:
            expected = whole_owner(state, sources[key], port)
            owners[state.spec.hu_id] = expected
            if containers[state.spec.hu_id].owner_id != expected:
                raise RuntimeError("Whole HU moved without completed physical handling")
        if state.admitted_tick is None:
            continue
        if state.shipped_tick is None:
            claim_id = "whole:" + key
            required_claims.add(claim_id)
            _claim(state, ledger)
        if state.returned_tick is None:
            worker = workers[str(state.actor_id)]
            if worker.order_id != key or worker.task != "whole":
                raise RuntimeError("Whole actor released before paid return")
            _receiver_operation(worker, tick)
        for resource in whole_resources(state, port):
            if resource in resources:
                raise RuntimeError("Whole resource has two physical owners")
            resources[resource] = key
        if state.buffer_picked_tick is None and any(
            c.owner_id == state.buffer_owner_id and c.container_id != state.spec.hu_id
            for c in containers.values()
        ):
            raise RuntimeError("Whole reserved buffer contains another HU")
    actual = {
        k: v
        for k, v in leases.items()
        if k.startswith("whole:") or (k.startswith("port:") and v in states)
    }
    if actual != resources:
        raise RuntimeError("Whole resource leases disagree with physical stages")
    return owners, frozenset(required_claims)


def _claim(state: WholeState, ledger: StockLedger) -> None:
    claim = next((c for c in ledger.claims if c.claim_id == "whole:" + state.spec.job_id), None)
    contents = ledger.contents(state.spec.hu_id)
    if (
        claim is None
        or not claim.whole_hu
        or claim.job_id != state.spec.job_id
        or claim.container_id != state.spec.hu_id
        or set(claim.unit_ids) != {u.token.unit_id for u in contents.units}
    ):
        raise RuntimeError("Whole physical job lost its exact inventory claim")
