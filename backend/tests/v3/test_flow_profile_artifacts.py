"""Published schema/example and the actual connected source runtime agree on physical stock."""

import json
from fractions import Fraction as F
from pathlib import Path

from jsonschema import Draft202012Validator

from app.v3.flow_profile import compile_light_profile
from app.v3.flow_profile_schema import profile_schema
from app.v3.light_flow_engine import LightFlowEngine
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


def test_published_schema_is_current_and_accepts_explicit_example() -> None:
    path = Path("docs/proposals/adaptive-v3/light-flow-profile.schema.json")
    published = json.loads(path.read_bytes())
    assert published == profile_schema()
    Draft202012Validator.check_schema(published)
    Draft202012Validator(published).validate(document())


def test_explicit_example_runs_three_original_units_without_inventory_creation() -> None:
    compiled = compile_light_profile(source_bundle(), source_catalog(), document())
    result = LightFlowEngine(compiled.profile, source_catalog()).run(
        compiled.horizon_tick, compiled.end_tick
    )
    assert result.status == "complete"
    assert result.at_end.balance.shipped_units_by_sku == (("DEMO_001", 3),)
    assert result.at_end.balance.gross_mass_kg == F(940410, 100)
    assert result.at_end.balance.shipped_mass_kg == F(155, 1000)
    assert not result.at_end.leases and not result.at_end.belt.leases
