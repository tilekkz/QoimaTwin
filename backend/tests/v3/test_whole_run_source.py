"""Repository-contained source binding is rebuilt without executing a source DES."""

from dataclasses import replace
from functools import cache

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.whole_profile_source import BoundWholeSource, bind_whole_source
from app.v3.whole_run_inputs import freeze_whole_source, load_whole_inputs
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_whole_profile_fixtures import whole_source_receipt_choices


@cache
def _source() -> BoundWholeSource:
    choices, buffers = whole_source_receipt_choices()
    return bind_whole_source(source_bundle(), source_catalog(), choices, buffers)


def test_source_outer_clock_identity_preserves_inner_exact_binder_bytes() -> None:
    bound = _source()
    inputs = freeze_whole_source(bound, 2_000_000_000, 4_000_000_000)
    outer = parse_json(inputs.frozen_bytes)
    assert canonical_bytes(outer["physical_inputs"]) == bound.frozen_bytes
    assert inputs.physical_input_hash == bound.input_hash
    assert inputs.input_hash != bound.input_hash
    assert len(inputs.profile.receipts.flow.stock.units) == 12256
    assert inputs.profile.receipts.ports[0].service_tick == 18_000_000
    assert dict(inputs.profile.ports[0].service_ticks)["STANDARD_CARTON"] == 35_000_000
    assert load_whole_inputs(inputs.frozen_bytes).input_hash == inputs.input_hash


def test_source_bound_profile_or_graph_cannot_be_swapped_under_valid_inner_hash() -> None:
    bound = _source()
    altered = replace(bound, profile=replace(bound.profile, pickup_tick=2_000_000))
    with pytest.raises(ValueError, match="profile"):
        freeze_whole_source(altered, 2_000_000_000, 4_000_000_000)
    with pytest.raises(ValueError, match="graph"):
        freeze_whole_source(replace(bound, graph_document=b"{}"), 2_000_000_000, 4_000_000_000)
