"""No source-anchor overrides, missing physical choices or ambiguous horizon boundary."""

import pytest

from app.v3.flow_profile import compile_light_profile
from app.v3.flow_profile_schema import validate_document
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_flow_profile_compiler import document


@pytest.mark.parametrize("parent,field", [("cart", "park"), ("station", "node")])
def test_nested_source_anchor_override_is_rejected(parent: str, field: str) -> None:
    value = document()
    value[parent][field] = "v3:service:CART_PARK"
    with pytest.raises(ValueError):
        validate_document(value)


@pytest.mark.parametrize("missing", ["pack_duration", "material_tare"])
def test_required_physical_choices_do_not_receive_defaults(missing: str) -> None:
    value = document()
    if missing == "pack_duration":
        del value["times"]["pack"]
    else:
        del value["recipes"][0]["tare_kg"]
    with pytest.raises(ValueError):
        validate_document(value)


@pytest.mark.parametrize("case", ["zero_horizon", "arrival_at_horizon"])
def test_offered_population_respects_positive_half_open_horizon(case: str) -> None:
    value = document()
    if case == "zero_horizon":
        value["horizon_tick"] = 0
    else:
        value["orders"][0]["arrival_tick"] = value["horizon_tick"]
    with pytest.raises(ValueError):
        compile_light_profile(source_bundle(), source_catalog(), value)


def test_one_tick_horizon_is_valid_without_fabricating_execution_results() -> None:
    value = document()
    value["horizon_tick"] = value["end_tick"] = 1
    result = compile_light_profile(source_bundle(), source_catalog(), value)
    assert result.horizon_tick == result.end_tick == 1
    assert result.profile.orders[0].arrival_tick == 0
    assert len(result.profile.stock.units) == 12256
    assert len(result.profile.materials) == 2
    assert result.profile.port.service_tick == 20_000_000
    assert b'"events"' not in result.frozen_bytes
