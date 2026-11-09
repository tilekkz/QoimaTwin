"""Explicit hand profiles test projection; public file tests use the real source compiler."""

from dataclasses import replace
from functools import cache

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.flow_profile import CompiledLightProfile
from app.v3.flow_profile_wire import materialized_record
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowOutcome
from app.v3.stock_ledger import StockLedger
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


@cache
def sample(boundary: bool = False) -> tuple[CompiledLightProfile, FlowOutcome]:
    profile = hand_profile()
    horizon, end = 50_000_000, 200_000_000
    if boundary:
        profile = replace(profile, orders=(replace(profile.orders[0], arrival_tick=47_000_000),))
        horizon = end = 61_000_000
    ledger = StockLedger(profile.stock, owners=profile.owners, materials=profile.materials)
    frozen = {
        "choices": {"horizon_tick": horizon, "end_tick": end},
        **materialized_record(profile, ledger),
    }
    compiled = CompiledLightProfile(
        profile, horizon, end, canonical_bytes(frozen), sha256_hex(frozen)
    )
    return compiled, LightFlowEngine(profile, source_catalog()).run(horizon, end)
