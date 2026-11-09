"""Raw source identity and the exact outbound-only derived authority."""

import shutil
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path

import pytest

from app.v3.outbound_shift_inputs import compile_outbound_shift
from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.workload_source import expected_port_totals
from tests.v3.test_outbound_shift_fixtures import ADAPTATION, BASE, POLICY, compiled

__all__ = ["compiled"]


def test_exact_baseline_assignment_and_full_raw_sources(compiled: OutboundShiftInputs) -> None:
    scenario = compiled.scenario
    raw = {entry.key: entry for entry in scenario.raw_sources}
    expected = {
        "c10_input": (
            BASE,
            "baseline-input-v3.json",
            "2abbaec208c3113c397d416a295b34bb29cd11f057fb4e34f3f8af6759a65cd1",
        ),
        "c10_assignment": (
            BASE,
            "baseline-assignment-v3.json",
            "576785a5893594517b4af5b8e888c7c20fe01c16c8ab901fd6191872a65c7939",
        ),
        "c11_input": (
            ADAPTATION,
            "adaptation-input-v3.json",
            "5b9f294e4ac3f36bd196dcde5853432f394a7276f9fc4256e4d59a1a9aed8e23",
        ),
    }
    for key, (root, name, digest) in expected.items():
        assert raw[key].raw == (root / "docs/v3/contract-proposals" / name).read_bytes()
        assert raw[key].raw_sha256 == sha256(raw[key].raw).hexdigest() == digest
    assert len(scenario.initial_placements) == 530
    assert len({p.hu_id for p in scenario.initial_placements}) == 530
    assert len(scenario.baseline.templates) == 200
    assert scenario.legacy_scenario_id == "N2_DECLARED_PORT_MIX_SHIFT"
    assert scenario.period_unit == "unclocked_planning_period"


def test_outbound_projection_preserves_c10_inbound_stock_and_intensity(
    compiled: OutboundShiftInputs,
) -> None:
    before, after = compiled.scenario.baseline, compiled.scenario.postshift
    assert before.templates == after.templates
    assert before.inbound_weights == after.inbound_weights
    assert dict(expected_port_totals(after.inbound_weights)) == {
        "IN_E_PARCEL": F("957.6"),
        "IN_N_STANDARD": F("304.4"),
        "IN_W_BULK": F(238),
    }
    assert dict(expected_port_totals(before.outbound_weights)) == {
        "OUT_W_RETAIL": F("787.7"),
        "OUT_S_EXPRESS": F("560.7"),
        "OUT_E_B2B": F("151.6"),
    }
    assert dict(expected_port_totals(after.outbound_weights)) == {
        "OUT_W_RETAIL": F("203.5"),
        "OUT_S_EXPRESS": F("1059.1"),
        "OUT_E_B2B": F("237.4"),
    }
    assert compiled.scenario.excluded_inbound_skus == tuple(f"DEMO_{i}" for i in range(111, 166))
    assert after.raw_fingerprints != before.raw_fingerprints
    assert all(type(w.weight) is F for w in after.outbound_weights)


def test_pinned_intensities_agree_before_using_global_mix_oracle(
    compiled: OutboundShiftInputs,
) -> None:
    from app.storage.canonical_json import parse_json

    docs = {entry.key: parse_json(entry.raw) for entry in compiled.scenario.raw_sources}
    before = {row["sku_id"]: row for row in docs["c10_input"]["skus"]}
    after = {row["sku_id"]: row for row in docs["c11_input"]["skus"]}
    assert before.keys() == after.keys()
    assert all(
        before[sku]["expected_outbound_HU_moves"] == after[sku]["expected_outbound_HU_moves"]
        for sku in before
    )


def test_wrong_raw_c11_source_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "adaptation"
    shutil.copytree(ADAPTATION, target)
    path = target / "docs/v3/contract-proposals/adaptation-input-v3.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="mismatch"):
        compile_outbound_shift(BASE, target, POLICY)
