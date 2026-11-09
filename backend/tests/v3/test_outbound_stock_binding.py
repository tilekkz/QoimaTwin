"""Source reauthentication and byte-exact allocation, without an engine or HTTP."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from shutil import copytree
from typing import Any, cast

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import outbound_stock_source
from app.v3.outbound_shift_inputs import compile_outbound_shift
from app.v3.outbound_stock_binding import (
    bind_outbound_stock,
    load_outbound_stock,
    verify_outbound_stock,
)
from app.v3.outbound_stock_models import BoundOutboundStock
from app.v3.workload_models import WorkloadPolicy


@pytest.fixture(scope="module")
def bound() -> BoundOutboundStock:
    data = Path(__file__).resolve().parents[2] / "data"
    inputs = compile_outbound_shift(
        data / "v3-proposal",
        data / "v3-adaptation-proposal",
        WorkloadPolicy(20, 4, 8, "normal"),
    )
    return bind_outbound_stock(inputs)


def test_source_binding_preserves_stock_and_exact_whole_offers(bound: BoundOutboundStock) -> None:
    assert len(bound.original_stock) == 530
    assert sum(hu.quantity_units for hu in bound.original_stock) == 12_256
    assert sum((hu.gross_mass_kg for hu in bound.original_stock), F(0)) == F("9403.85")
    expected = tuple(j for j in bound.inputs.workload.jobs if j.direction == "outbound")
    assert tuple(row.offer for row in bound.allocations) == expected
    assert len(bound.declared_receipts) == 4 and len(bound.allocations) == 8
    assert not bound.operational_admission and not bound.full_n1_acceptance
    restored = load_outbound_stock(bound.frozen_bytes)
    assert restored == bound and restored is not bound
    assert verify_outbound_stock(bound) == bound
    assert bind_outbound_stock(bound.inputs).frozen_bytes == bound.frozen_bytes


@pytest.mark.parametrize("raw", [None, "{}", bytearray(b"{}"), b"[]", b"{}"])
def test_wrong_input_types_and_shape_fail_closed(raw: Any) -> None:
    with pytest.raises(ValueError):
        load_outbound_stock(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity_units", True),
        ("initial_owner_id", "invented-slot"),
        ("unit_ids", ["invented-unit"]),
        ("lot_id", "invented-lot"),
    ],
)
def test_wire_stock_edits_cannot_inherit_source_authority(
    bound: BoundOutboundStock,
    field: str,
    value: object,
) -> None:
    document = parse_json(bound.frozen_bytes)
    document["original_stock"][0][field] = value
    with pytest.raises(ValueError):
        load_outbound_stock(canonical_bytes(document))


def test_retained_stock_and_offer_changes_are_revalidated(bound: BoundOutboundStock) -> None:
    hu = bound.original_stock[0]
    for changed in (
        replace(hu, quantity_units=True),
        replace(hu, gross_mass_kg=cast(Any, float(hu.gross_mass_kg))),
    ):
        forged = replace(bound, original_stock=(changed, *bound.original_stock[1:]))
        with pytest.raises(ValueError):
            verify_outbound_stock(forged)
    row = bound.allocations[0]
    forged_row = replace(row, offer=replace(row.offer, arrival_tick=True))
    with pytest.raises(ValueError):
        verify_outbound_stock(replace(bound, allocations=(forged_row, *bound.allocations[1:])))


def test_forged_shift_and_noncanonical_wire_are_rejected(bound: BoundOutboundStock) -> None:
    forged_workload = replace(bound.inputs.workload, jobs=())
    with pytest.raises(ValueError):
        bind_outbound_stock(replace(bound.inputs, workload=forged_workload))
    with pytest.raises(ValueError):
        load_outbound_stock(bound.frozen_bytes + b"\n")
    document = parse_json(bound.frozen_bytes)
    document["operational_admission"] = 0
    with pytest.raises(ValueError):
        load_outbound_stock(canonical_bytes(document))


def test_saved_binding_reopens_and_revalidates_original_raw_stock(
    bound: BoundOutboundStock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replica = tmp_path / "source-copy"
    copytree(Path(__file__).resolve().parents[2] / "data/v3-proposal", replica)
    monkeypatch.setattr(outbound_stock_source, "_base_root", lambda: replica)
    assert verify_outbound_stock(bound) == bound
    assignment = replica / "docs/v3/contract-proposals/baseline-assignment-v3.json"
    assignment.write_bytes(assignment.read_bytes() + b" ")
    with pytest.raises(ValueError, match="pinned bytes/SHA256 mismatch"):
        verify_outbound_stock(bound)


@pytest.mark.parametrize("mutation", ["remove", "duplicate", "arrival", "receipt"])
def test_wire_cannot_truncate_clone_or_retime_offers(
    bound: BoundOutboundStock,
    mutation: str,
) -> None:
    document = parse_json(bound.frozen_bytes)
    rows = document["allocations"]
    if mutation == "remove":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(rows[0])
    elif mutation == "arrival":
        rows[0]["offer"]["arrival_tick"] += 1
    else:
        document["declared_receipts"][0]["receipt_job_id"] = "invented"
    with pytest.raises(ValueError):
        load_outbound_stock(canonical_bytes(document))
