"""Compiler input admission: engine-level identities and plain decimal numeric text.

- A buffer place ID equal to a storage-slot ID must fail in the compiler, before
  `materialize_manual` can report "passed" (review finding F3).
- Synthetic numeric choices are plain finite decimal text: fraction, underscore and
  whitespace spellings are rejected (finding F5). Ordinary decimal and exponent spellings
  and the ADR 0032 calendar ceiling stay accepted. Different legitimate strings may still
  hash differently: the input hash binds the explicit proposal text and provenance.
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.materialize import calendar_tick, number
from app.v3.profile import compile_manual_profile
from app.v3.profile_models import ManualProposal

DATA = Path(__file__).parents[2] / "data"


@pytest.fixture(scope="module")
def bundle() -> V3Bundle:
    return load_v3_bundle(DATA / "v3-proposal")


def test_buffer_id_equal_to_a_storage_slot_id_fails_in_the_compiler(bundle: V3Bundle) -> None:
    raw = json.loads((DATA / "v3-execution-proposals/manual-whole-hu-demo-v1.json").read_bytes())
    raw["buffers"][0]["place_id"] = "v3:slot:SMALL_W:001:L1:B1"
    with pytest.raises(ValueError, match="duplicate execution identifier"):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


@pytest.mark.parametrize(
    "text", ["13/10", " 1.3", "1.3 ", "1_3e-1", "1.3\n", "+1.3", "", ".", "1e999999999"]
)
def test_non_decimal_numeric_spellings_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        number(text)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1.3", Fraction(13, 10)),
        ("13e-1", Fraction(13, 10)),
        ("1E+2", Fraction(100)),
        ("0.70", Fraction(7, 10)),
    ],
)
def test_ordinary_decimal_and_exponent_spellings_are_accepted(text: str, value: Fraction) -> None:
    assert number(text) == value


def test_calendar_ceiling_policy_is_unchanged() -> None:
    assert calendar_tick("1.0000001") == 1_000_001
    assert calendar_tick("0") == 0
