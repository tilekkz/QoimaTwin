"""Mixed terminal promises use manual capacity arithmetic, not engine timing oracles."""

from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.stock_models import StockOwner
from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_flow_models import WholeFlowOutcome, WholeFlowProfile
from app.v3.whole_run import build_whole_run, validate_whole_run
from app.v3.whole_run_inputs import WholeRunInputs, freeze_hand_inputs
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


class FaultyTerminalProducer(WholeFlowEngine):
    """Reproduce the old admission bug while retaining all unrelated runtime guards."""

    def _has_owner_capacity(self, owner_id: str) -> bool:
        reserved = sum(
            self.whole_ports[s.spec.port_id].shipped_owner == owner_id
            and s.port_reserved_tick is not None
            and s.shipped_tick is None
            for s in self.whole_orders.values()
        )
        occupied = sum(c.owner_id == owner_id for c in self.ledger.snapshot().containers)
        return occupied + reserved < self.owner_specs[owner_id].capacity

    def _check_shipped_capacity(self) -> None:
        """Only the new terminal check is bypassed to produce a malformed test trace."""


def mixed_profile(capacity: int = 1, *, separate_owner: bool = False) -> WholeFlowProfile:
    profile, receipt = whole_hand_profile("SMALL_CARTON"), receipt_hand_profile()
    flow = profile.receipts.flow
    owners = tuple(
        replace(owner, capacity=capacity) if owner.owner_id == "shipped" else owner
        for owner in flow.owners
    )
    if separate_owner:
        owners += (StockOwner("shipped:extra", "shipped", 1),)
    flow = replace(flow, orders=hand_orders(1), owners=owners)
    port = profile.ports[0]
    if separate_owner:
        port = replace(port, shipped_owner="shipped:extra")
    return replace(
        profile,
        receipts=replace(receipt, flow=flow),
        orders=(replace(profile.orders[0], hu_id="HU2", arrival_tick=173 * SECOND),),
        places=(*profile.places, next(p for p in receipt.places if p.owner_id == "new-slot")),
        ports=(port,),
    )


@cache
def mixed_trace(
    capacity: int = 1, *, end: int = 181, separate_owner: bool = False
) -> tuple[WholeRunInputs, WholeFlowOutcome]:
    profile = mixed_profile(capacity, separate_owner=separate_owner)
    conveyor = receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 181 * SECOND, end * SECOND)
    return inputs, FaultyTerminalProducer(profile, conveyor).run(181 * SECOND, end * SECOND)


def test_strict_publication_rejects_two_promises_for_one_terminal_place(tmp_path: Path) -> None:
    inputs, outcome = mixed_trace()
    worker = next(w for w in outcome.at_end.workers if w.actor_id == "S01")
    assert worker.operation is not None and worker.operation.kind == "shipping_service"
    assert (worker.operation.start_tick, worker.operation.planned_end_tick) == (
        172_170_000,
        192_170_000,
    )
    assert outcome.at_end.whole_orders[0].port_reserved_tick == 180_000_000
    run = build_whole_run(inputs, outcome, validate=False)
    (tmp_path / "inputs.json").write_bytes(inputs.frozen_bytes)
    (tmp_path / "run.json").write_bytes(canonical_bytes(run))
    with pytest.raises(ValueError, match="terminal capacity"):
        validate_whole_run(run)


@pytest.mark.parametrize("end", [181, 220])
def test_two_terminal_places_allow_mixed_partial_and_actual_handoffs(end: int) -> None:
    inputs, outcome = mixed_trace(2, end=end)
    run = build_whole_run(inputs, outcome)
    assert run["status"] == ("partial" if end == 181 else "complete")
    if end == 220:
        placed = [
            c for c in run["at_end"]["state"]["stock"]["containers"] if c["owner_id"] == "shipped"
        ]
        assert {c["container_id"] for c in placed} == {"P1", "HU2"}


def test_prefix_related_owner_ids_have_independent_terminal_capacities() -> None:
    inputs, outcome = mixed_trace(separate_owner=True)
    assert build_whole_run(inputs, outcome)["status"] == "partial"
