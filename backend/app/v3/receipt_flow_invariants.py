"""The single accounting authority must match actual receipt stages and resource claims."""

from collections import Counter
from collections.abc import Mapping

from app.v3.light_flow_state import HumanState, OrderState
from app.v3.receipt_flow_models import ReceiptFlowProfile
from app.v3.receipt_flow_state import ReceiptState
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container


def check_receipt_world(
    profile: ReceiptFlowProfile,
    states: Mapping[str, ReceiptState],
    workers: Mapping[str, HumanState],
    leases: Mapping[str, str],
    ledger: StockLedger,
    orders: Mapping[str, OrderState],
    pick_claims: Mapping[str, str],
    tick: int,
    *,
    whole_owners: Mapping[str, str] | None = None,
    whole_claims: frozenset[str] = frozenset(),
) -> None:
    expected = Counter(u.sku_id for u in profile.flow.stock.units)
    containers = {c.container_id: c for c in ledger.snapshot().containers}
    _baseline_owners(profile, containers, whole_owners)
    _pending_picks(states, orders, pick_claims, ledger, whole_claims)
    resources: dict[str, str] = {}
    for key, state in states.items():
        _custody(state, containers, whole_owners)
        if state.credited_tick is not None:
            expected[state.offer.definition.sku_id] += state.offer.definition.quantity_units
        if state.admitted_tick is not None and state.returned_tick is None:
            worker = workers[str(state.actor_id)]
            _receiver_operation(worker, tick)
            if worker.order_id != key or worker.task != "receipt":
                raise RuntimeError("Receipt actor was duplicated or released before return")
            for resource in _required_resources(state, worker):
                if resource in resources:
                    raise RuntimeError("Receipt resource has two physical owners")
                resources[resource] = key
        _claim(state, ledger)
    actual = {key: owner for key, owner in leases.items() if key.startswith("receipt:")}
    _reserved_places(resources, states, containers)
    if actual != resources:
        raise RuntimeError("Receipt resource leases disagree with physical stages")
    if dict(expected) != dict(ledger.balance().units_by_sku):
        raise RuntimeError("Initial plus credited receipts must equal registered stock")


def _custody(
    state: ReceiptState,
    containers: Mapping[str, Container],
    whole_owners: Mapping[str, str] | None = None,
) -> None:
    hu = state.offer.definition.hu_id
    if (hu in containers) != (state.credited_tick is not None):
        raise RuntimeError("Receipt stock exists before credit or vanished afterwards")
    if state.credited_tick is None:
        return
    expected: str | None
    if state.placed_tick is not None:
        expected = (whole_owners or {}).get(hu, state.offer.slot_owner_id)
    elif state.status == "buffered":
        expected = state.buffer_owner_id
    else:
        expected = "actor:" + str(state.actor_id)
    if containers[hu].owner_id != expected:
        raise RuntimeError("Receipt HU custody disagrees with completed physical handling")


def _required_resources(state: ReceiptState, worker: HumanState) -> tuple[str, ...]:
    result = ["receipt:worker:" + str(state.actor_id)]
    if state.placed_tick is None:
        result.extend(
            (
                "receipt:place:" + state.offer.slot_owner_id,
                "receipt:hu:" + state.offer.definition.hu_id,
            )
        )
    if not state.buffer_released:
        result.append("receipt:place:" + str(state.buffer_owner_id))
    if worker.operation is not None and worker.operation.kind == "receipt_service":
        result.append("receipt:port:" + state.offer.port_id)
    return tuple(result)


def _claim(state: ReceiptState, ledger: StockLedger) -> None:
    key = state.offer.definition.receipt_id
    claim = next((c for c in ledger.claims if c.claim_id == "receipt:" + key), None)
    required = state.credited_tick is not None and state.placed_tick is None
    if (claim is not None) != required:
        raise RuntimeError("Receipt whole-HU claim released before physical putaway")
    if claim is not None and (
        claim.job_id != key
        or not claim.whole_hu
        or claim.container_id != state.offer.definition.hu_id
        or len(claim.unit_ids) != state.offer.definition.quantity_units
    ):
        raise RuntimeError("Receipt whole-HU claim has incorrect physical contents")


def _reserved_places(
    resources: Mapping[str, str],
    states: Mapping[str, ReceiptState],
    containers: Mapping[str, Container],
) -> None:
    for resource, job_id in resources.items():
        if not resource.startswith("receipt:place:"):
            continue
        owner = resource.removeprefix("receipt:place:")
        permitted_hu = states[job_id].offer.definition.hu_id
        if any(c.owner_id == owner and c.container_id != permitted_hu for c in containers.values()):
            raise RuntimeError("Receipt reserved place is occupied by another physical HU")


def _baseline_owners(
    profile: ReceiptFlowProfile,
    containers: Mapping[str, Container],
    whole_owners: Mapping[str, str] | None = None,
) -> None:
    for initial in profile.flow.stock.containers:
        expected = (whole_owners or {}).get(initial.container_id, initial.owner_id)
        if containers[initial.container_id].owner_id != expected:
            raise RuntimeError("Receipt unit-only flow cannot move a baseline whole wrapper")


def _receiver_operation(worker: HumanState, tick: int) -> None:
    operation = worker.operation
    if operation is None:
        return
    if not worker.steps:
        raise RuntimeError("Receipt operation lacks its physical plan")
    step = worker.steps[0]
    if (
        operation.kind != step.kind
        or operation.target_node != step.target
        or operation.carrying_id != step.carrying_id
        or operation.cart_id != step.cart_id
        or operation.route is not step.route
        or type(operation.start_tick) is not int
        or type(operation.planned_end_tick) is not int
        or not 0 <= operation.start_tick <= tick < operation.planned_end_tick
        or operation.planned_end_tick - operation.start_tick != step.duration
    ):
        raise RuntimeError("Receipt operation disagrees with its actual planned motion")


def _pending_picks(
    states: Mapping[str, ReceiptState],
    orders: Mapping[str, OrderState],
    pick_claims: Mapping[str, str],
    ledger: StockLedger,
    whole_claims: frozenset[str] = frozenset(),
) -> None:
    claims = {c.claim_id: c for c in ledger.claims}
    expected = (
        {
            "receipt:" + key
            for key, state in states.items()
            if state.credited_tick is not None and state.placed_tick is None
        }
        | set(pick_claims.values())
        | whole_claims
    )
    if set(claims) != expected:
        raise RuntimeError("Receipt flow inventory claims disagree with actual pending jobs")
    for job_id, claim_id in pick_claims.items():
        order, claim = orders[job_id], claims[claim_id]
        if (
            order.status != "picking"
            or claim.whole_hu
            or claim.job_id != job_id
            or claim.container_id != order.spec.source_hu
            or set(claim.unit_ids) != {p.unit_id for p in order.spec.carrier_placements}
        ):
            raise RuntimeError("Receipt flow pick claim disagrees with admitted exact units")
