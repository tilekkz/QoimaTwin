"""Rehashed metadata and numeric aliases cannot replace fresh source authority."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.long_freight_binding import (
    compile_long_freight_requirements,
    load_long_freight_requirements,
    verify_long_freight_requirements,
)
from app.v3.long_freight_models import LongFreightRequirements
from tests.v3.test_long_freight_inputs import policy, request


@pytest.fixture(scope="module")
def bound() -> LongFreightRequirements:
    return compile_long_freight_requirements(request(), policy())


def test_fresh_roundtrip_recomputes_every_source_and_offer(bound: LongFreightRequirements) -> None:
    fresh = verify_long_freight_requirements(bound)
    assert fresh == bound and fresh is not bound
    assert fresh.authority is not bound.authority
    assert fresh.authority.workload_bytes == bound.authority.workload_bytes
    assert load_long_freight_requirements(bound.frozen_bytes) == bound


@pytest.mark.parametrize("field,value", [("operational_admission", True), ("unknown", 0)])
def test_rehashed_flags_and_extra_fields_fail_closed(
    bound: LongFreightRequirements,
    field: str,
    value: Any,
) -> None:
    wire = parse_json(bound.frozen_bytes)
    wire[field] = value
    with pytest.raises(ValueError):
        load_long_freight_requirements(canonical_bytes(wire))


def test_rehashed_mass_and_arrival_do_not_get_adopted(bound: LongFreightRequirements) -> None:
    for key in ("mass", "arrival"):
        wire = parse_json(bound.frozen_bytes)
        if key == "mass":
            wire["static"]["hu_mass_kg"]["numerator"] = 201
        else:
            wire["authority"]["workload"]["jobs"][0]["arrival_tick"] += 1
        with pytest.raises(ValueError):
            load_long_freight_requirements(canonical_bytes(wire))


def test_retained_equal_numeric_aliases_and_shortened_stock_reject(
    bound: LongFreightRequirements,
) -> None:
    for changed in (
        replace(bound, operational_admission=0),  # type: ignore[arg-type]
        replace(bound, static=replace(bound.static, hu_mass_kg=200)),  # type: ignore[arg-type]
        replace(
            bound, authority=replace(bound.authority, initial_hus=bound.authority.initial_hus[:-1])
        ),
    ):
        with pytest.raises(ValueError):
            verify_long_freight_requirements(changed)


def test_fresh_public_verify_reopens_raw_source(
    bound: LongFreightRequirements,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = original(path)
        return raw + b" " if path.name == "vehicle-handling-v3.json" else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="SHA256"):
        verify_long_freight_requirements(bound)


def test_request_and_policy_types_are_exact() -> None:
    with pytest.raises(ValueError):
        compile_long_freight_requirements(replace(request(), actor_id=True), policy())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compile_long_freight_requirements(request(), replace(policy(), inbound_hus=True))
