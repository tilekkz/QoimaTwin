"""Source compiler identities and accounting are specified before any DES execution."""

from copy import deepcopy
from fractions import Fraction as F

import pytest

from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.settings import default_inputs
from app.v3.whole_profile_io import compile_whole_profile
from tests.v3.test_whole_profile_io_schema import document

Sources = tuple[V3Bundle, ConveyorSource]


@pytest.fixture(scope="module")
def sources() -> Sources:
    bundle = load_v3_bundle(default_inputs())
    return bundle, load_conveyor_source(bundle)


def test_source_example_has_baseline_only_and_source_service(sources: Sources) -> None:
    compiled = compile_whole_profile(*sources, document())
    inputs = compiled.run_inputs
    profile = inputs.profile
    assert inputs.horizon_tick == 2_000_000_000
    assert inputs.end_tick == 4_000_000_000
    assert len(profile.receipts.flow.stock.containers) == 530
    assert len(profile.receipts.flow.stock.units) == 12_256
    assert len(profile.receipts.flow.actors) == 24
    assert profile.receipts.ports[0].service_tick == 18_000_000
    assert dict(profile.ports[0].service_ticks)["STANDARD_CARTON"] == 35_000_000
    assert profile.receipts.flow.actors[0].speed_m_s == F(1)


def test_set_permutation_and_reduced_rationals_preserve_both_identities(sources: Sources) -> None:
    original = document()
    changed = deepcopy(original)
    for key in ("actors", "owners", "materials", "recipes", "whole_ports", "receipt_buffers"):
        changed[key].reverse()
    changed["whole_ports"][0]["shipper_ids"].reverse()
    changed["actors"][0]["speed_m_s"] = {"numerator": 2, "denominator": 2}
    a = compile_whole_profile(*sources, original)
    b = compile_whole_profile(*sources, changed)
    assert a.choices_bytes == b.choices_bytes
    assert a.run_inputs.frozen_bytes == b.run_inputs.frozen_bytes
    changed["whole_times"]["pickup"] += 1
    c = compile_whole_profile(*sources, changed)
    assert a.choices_sha256 != c.choices_sha256
    assert a.run_inputs.input_hash != c.run_inputs.input_hash


@pytest.mark.parametrize("table", ["whole_orders", "receipts", "whole_buffers", "owners"])
def test_duplicate_choices_reject(sources: Sources, table: str) -> None:
    value = document()
    value[table].append(deepcopy(value[table][0]))
    with pytest.raises(ValueError):
        compile_whole_profile(*sources, value)


@pytest.mark.parametrize("table", ["whole_orders", "receipts"])
def test_arrival_at_horizon_rejects_before_source_binding(sources: Sources, table: str) -> None:
    value = document()
    value[table][0]["arrival_tick"] = value["horizon_tick"]
    with pytest.raises(ValueError, match="arrival"):
        compile_whole_profile(*sources, value)


@pytest.mark.parametrize("case", ["unknown_hu", "wrong_buffer", "heavy_receipt", "end_before_h"])
def test_invalid_operational_choices_reject(sources: Sources, case: str) -> None:
    value = document()
    if case == "unknown_hu":
        value["whole_orders"][0]["hu_id"] = "unknown"
    elif case == "wrong_buffer":
        value["whole_buffers"][0]["port_id"] = "OUT_S_EXPRESS"
    elif case == "heavy_receipt":
        value["receipts"][0]["sku_id"] = "DEMO_166"
    else:
        value["end_tick"] = value["horizon_tick"] - 1
    with pytest.raises(ValueError):
        compile_whole_profile(*sources, value)
