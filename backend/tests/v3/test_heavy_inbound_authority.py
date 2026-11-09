"""Strict fresh authority rejects rehashed future stream and retained numeric aliases."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.heavy_inbound_binding import (
    compile_heavy_inbound_inputs,
    load_heavy_inbound_inputs,
    verify_heavy_inbound_inputs,
)
from app.v3.heavy_inbound_models import HeavyInboundInputs
from tests.v3.test_heavy_inbound_hand import additions as hand_additions
from tests.v3.test_heavy_inbound_hand import baseline as hand_baseline
from tests.v3.test_heavy_inbound_inputs import additions, policy


@pytest.fixture(scope="module")
def bound() -> HeavyInboundInputs:
    return compile_heavy_inbound_inputs(policy(), additions())


def test_public_roundtrip_reauthenticates_fresh_c10(bound: HeavyInboundInputs) -> None:
    fresh = verify_heavy_inbound_inputs(bound)
    assert fresh == bound and fresh is not bound
    assert fresh.authority is not bound.authority
    assert load_heavy_inbound_inputs(bound.frozen_bytes) == bound


@pytest.mark.parametrize("field", ["arrival_tick", "quantity_units"])
def test_rehashed_postshift_offer_mutation_is_rejected(
    bound: HeavyInboundInputs, field: str
) -> None:
    wire = parse_json(bound.frozen_bytes)
    wire["postshift_jobs"][0][field] += 1
    with pytest.raises(ValueError):
        load_heavy_inbound_inputs(canonical_bytes(wire))


@pytest.mark.parametrize("field,value", [("operational_admission", True), ("extra", 0)])
def test_canonical_metadata_has_no_extra_authority(
    bound: HeavyInboundInputs,
    field: str,
    value: Any,
) -> None:
    wire = parse_json(bound.frozen_bytes)
    wire[field] = value
    with pytest.raises(ValueError):
        load_heavy_inbound_inputs(canonical_bytes(wire))


def test_retained_equal_numeric_aliases_and_receipt_mass_do_not_alias(
    bound: HeavyInboundInputs,
) -> None:
    first = bound.receipts[0]
    wrong = replace(first, template=replace(first.template, gross_mass_kg=455))  # type: ignore[arg-type]
    for value in (
        replace(bound, accepted_receipt_count=False),  # type: ignore[arg-type]
        replace(bound, receipts=(wrong, *bound.receipts[1:])),
        replace(
            bound, authority=replace(bound.authority, initial_hus=bound.authority.initial_hus[:-1])
        ),
    ):
        with pytest.raises(ValueError):
            verify_heavy_inbound_inputs(value)


def test_hand_augmentation_cannot_be_promoted_into_public_source(
    bound: HeavyInboundInputs,
) -> None:
    value = replace(bound, authority=replace(bound.authority, baseline=hand_baseline()))
    with pytest.raises(ValueError):
        verify_heavy_inbound_inputs(value)
    with pytest.raises(ValueError):
        compile_heavy_inbound_inputs(policy(), hand_additions())


def test_public_verification_reads_raw_baseline_again(
    bound: HeavyInboundInputs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = original(path)
        return raw + b" " if path.name == "baseline-input-v3.json" else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_heavy_inbound_inputs(bound)
