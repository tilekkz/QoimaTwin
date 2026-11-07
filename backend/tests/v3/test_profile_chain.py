"""Received-HU-then-outbound chain in the source compiler (ADR 0031: "the same received HU
may have a later outbound job"; review finding D4).

Expected units come from source recipes (baseline HU quantities and the receipt template),
never from engine output. Arrival ticks use the ADR 0032 microsecond ceiling.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.v3.execution import ManualEngine
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.materialize import materialize_jobs
from app.v3.materialize_manifest import materialized_bytes
from app.v3.profile import compile_manual_profile, load_manual_profile
from app.v3.profile_models import ManualProposal

DATA = Path(__file__).parents[2] / "data"
PROPOSAL = DATA / "v3-execution-proposals/manual-whole-hu-demo-v1.json"
RECEIPT_HU, RECEIPT_SLOT = "synthetic:HU:receipt:1", "v3:slot:SMALL_W:017:L1:B1"
TEMPLATE_HU = "v3:HU:initial:DEMO_001:01"


@pytest.fixture(scope="module")
def bundle() -> V3Bundle:
    return load_v3_bundle(DATA / "v3-proposal")


def _raw() -> Any:
    return json.loads(PROPOSAL.read_bytes())


def _chain(raw: Any, *, arrival: str = "120", slot: str = RECEIPT_SLOT) -> Any:
    raw["jobs"].append(
        {
            "job_id": "demo:ship:receipt:1",
            "arrival_seconds": arrival,
            "direction": "outbound",
            "hu_id": RECEIPT_HU,
            "port_id": "OUT_S_EXPRESS",
            "slot_id": slot,
            "receipt_template_hu_id": None,
        }
    )
    return raw


def _expected_final(bundle: V3Bundle, raw: Any) -> tuple[Counter[str], Counter[str]]:
    """Per-SKU (stock, shipped) after every job completes, from source recipes only."""
    source = {h.handling_unit_id: (h.sku_id, h.quantity_units) for h in bundle.handling_units}
    stock: Counter[str] = Counter()
    for sku, quantity in source.values():
        stock[sku] += quantity
    origin = dict(source)
    for job in raw["jobs"]:
        if job["direction"] == "inbound":
            origin[job["hu_id"]] = source[job["receipt_template_hu_id"]]
            stock[origin[job["hu_id"]][0]] += origin[job["hu_id"]][1]
    shipped: Counter[str] = Counter()
    for job in raw["jobs"]:
        if job["direction"] == "outbound":
            sku, quantity = origin[job["hu_id"]]
            stock[sku] -= quantity
            shipped[sku] += quantity
    return +stock, shipped


def test_receipt_then_ship_compiles_one_identity_and_conserves_every_sku(
    bundle: V3Bundle,
) -> None:
    # Test-only explicit boundaries: the default H=600 s ends this chain honestly partial
    # (shippers are busy first). A full hour lets every declared job finish; no timing oracle.
    raw = _chain(_raw()) | {"horizon_tick": 3_600_000_000, "end_tick": 5_400_000_000}
    inputs = compile_manual_profile(bundle, ManualProposal.model_validate(raw))
    profile = inputs.profile
    assert len(profile.initial_placements) == 530
    assert len(profile.handling_units) == 532  # no second clone for the outbound leg
    assert sum(1 for h in profile.handling_units if h.hu_id == RECEIPT_HU) == 1
    assert [j.hu_id for j in profile.jobs].count(RECEIPT_HU) == 2
    result = ManualEngine(profile, inputs.graph, check_invariants=True).run(
        inputs.horizon_tick, inputs.end_tick
    )
    stock, shipped = _expected_final(bundle, raw)
    assert sum(stock.values()) + sum(shipped.values()) == 12_256 + 48
    # Independent source-only oracle (subagent): DEMO_001 96 + 24 - 48 = 72; 72 units shipped.
    assert (stock["DEMO_001"], shipped["DEMO_001"], sum(shipped.values())) == (72, 48, 72)
    assert dict(result.at_end.shipped_units) == dict(shipped)
    assert dict(result.at_end.stock_units) == dict(stock)
    assert result.at_end.wip_units == result.at_end.outside_units == ()
    assert result.at_end.status == "complete"


def test_four_job_frozen_materialization_stays_byte_identical() -> None:
    compiled = load_manual_profile(DATA / "v3-proposal", PROPOSAL)
    assert materialized_bytes(compiled) == PROPOSAL.with_suffix(".materialized.json").read_bytes()


def test_chain_materializes_with_ceiling_and_simultaneous_arrivals() -> None:
    raw = _chain(_raw(), arrival="0")  # same tick as its receipt; waits for stock
    jobs = materialize_jobs(ManualProposal.model_validate(raw))
    chain = [j for j in jobs if j.hu_id == RECEIPT_HU]
    assert [(j.direction, j.arrival_tick) for j in chain] == [("inbound", 0), ("outbound", 0)]
    late = _chain(_raw(), arrival="1.0000001")  # ADR 0032 calendar ceiling
    ship = [
        j for j in materialize_jobs(ManualProposal.model_validate(late)) if j.hu_id == RECEIPT_HU
    ]
    assert ship[-1].arrival_tick == 1_000_001


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("outbound_before_receipt", "before"),
        ("second_receipt_same_hu", "per direction"),
        ("outbound_template_clone", "unique new HU"),
    ],
)
def test_chain_shape_rejections_before_engine(bundle: V3Bundle, change: str, message: str) -> None:
    raw = _raw()
    receipt = next(j for j in raw["jobs"] if j["hu_id"] == RECEIPT_HU)
    receipt["arrival_seconds"] = "30"
    _chain(raw, arrival="10" if change == "outbound_before_receipt" else "120")
    if change == "second_receipt_same_hu":
        raw["jobs"].append({**receipt, "job_id": "dup", "slot_id": "v3:slot:SMALL_W:018:L1:B1"})
    if change == "outbound_template_clone":
        raw["jobs"][-1]["receipt_template_hu_id"] = TEMPLATE_HU
    with pytest.raises(ValueError, match=message):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))


def test_outbound_of_a_receipt_must_use_its_receipt_slot(bundle: V3Bundle) -> None:
    raw = _chain(_raw(), slot="v3:slot:SMALL_W:018:L1:B1")
    with pytest.raises(ValueError, match="origin"):
        compile_manual_profile(bundle, ManualProposal.model_validate(raw))
