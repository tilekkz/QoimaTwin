"""Reject unknown references, source mismatches and unsafe synthetic choices."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.profile import compile_manual_profile
from app.v3.profile_models import ManualProposal

DATA = Path(__file__).parents[2] / "data"


@pytest.fixture(scope="module")
def bundle() -> V3Bundle:
    return load_v3_bundle(DATA / "v3-proposal")


def choices() -> Any:
    return json.loads((DATA / "v3-execution-proposals/manual-whole-hu-demo-v1.json").read_bytes())


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_revision", "changed"),
        ("pickup_seconds", "0"),
        ("place_seconds", "inf"),
        ("carry_width_m", "0.6"),
    ],
)
def test_bad_profile_choices(bundle: V3Bundle, field: str, value: str) -> None:
    raw = choices()
    raw[field] = value
    with pytest.raises(ValueError):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot_id", "unknown"),
        ("port_id", "IN_W_BULK"),
        ("direction", "split"),
        ("hu_id", "unknown"),
        ("slot_id", "v3:slot:STANDARD_E:007:L1:B2"),
    ],
)
def test_bad_job_references(bundle: V3Bundle, field: str, value: str) -> None:
    raw = choices()
    raw["jobs"][0][field] = value
    with pytest.raises(ValueError):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


def test_source_digest_mismatch(bundle: V3Bundle) -> None:
    raw = choices()
    raw["source_hashes"][0][1] = "0" * 64
    with pytest.raises(ValueError, match="hashes"):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


def test_connector_cannot_cross_rack_zone(bundle: V3Bundle) -> None:
    raw = choices()
    raw["buffers"][0]["path_xz"] = [["138", "54"], ["130", "54"], ["130", "59"]]
    with pytest.raises(ValueError, match="forbidden zone"):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


def test_no_teleport_connector(bundle: V3Bundle) -> None:
    raw = choices()
    raw["buffers"][0]["path_xz"] = [["130", "59"]]
    with pytest.raises(ValueError, match="actual service"):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("home_node_id", "unknown"),
        ("speed_m_s", "1.4"),
        ("max_gross_mass_kg", "0"),
        ("max_gross_mass_kg", "nan"),
    ],
)
def test_actor_choices_fail_closed(bundle: V3Bundle, field: str, value: str) -> None:
    raw = choices()
    raw["actors"][0][field] = value
    with pytest.raises(ValueError):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


def test_heavy_job_rejects_without_removing_heavy_stock(bundle: V3Bundle) -> None:
    raw = choices()
    hu = next(h for h in bundle.handling_units if h.archetype_id == "HEAVY_BOX")
    raw["jobs"][0].update(hu_id=hu.handling_unit_id, slot_id=hu.slot_id)
    with pytest.raises(ValueError, match="unsupported manual job cargo"):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))
