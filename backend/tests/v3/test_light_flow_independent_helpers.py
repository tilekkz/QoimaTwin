"""Observation helpers only; expected quantities/times come from the pre-engine oracle."""

from fractions import Fraction

from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowOutcome, FlowProfile, FlowSnapshot
from app.v3.stock_models import Container
from tests.v3.test_belt_runtime import source_catalog

SECOND = 1_000_000


def run_flow(profile: FlowProfile, horizon: int, end: int) -> FlowOutcome:
    return LightFlowEngine(profile, source_catalog()).run(horizon, end)


def container(snapshot: FlowSnapshot, identity: str) -> Container:
    return next(c for c in snapshot.stock.containers if c.container_id == identity)


def unit_ids(snapshot: FlowSnapshot, identity: str) -> frozenset[str]:
    return frozenset(
        row.unit_id for row in snapshot.stock.locations if row.container_id == identity
    )


def transaction_ticks(outcome: FlowOutcome, operation: str) -> tuple[int, ...]:
    return tuple(
        e.tick for e in outcome.events if e.delta is not None and e.delta.operation == operation
    )


def assert_whole_material_mass(snapshot: FlowSnapshot, expected: Fraction) -> None:
    balance = snapshot.balance
    assert balance.gross_mass_kg == expected
    assert balance.gross_mass_kg == (
        balance.contents_mass_kg + balance.primary_tare_kg + balance.container_tare_kg
    )
    assert dict(balance.units_by_sku) == {"SKU1": 24}
