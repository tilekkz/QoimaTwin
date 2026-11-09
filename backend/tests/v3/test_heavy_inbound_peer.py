"""Independent N2 identity, append-only and fresh-source controls; no receipt execution."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3.heavy_inbound_augment import augment_offers
from app.v3.heavy_inbound_binding import (
    compile_heavy_inbound_inputs,
    load_heavy_inbound_inputs,
    verify_heavy_inbound_inputs,
)
from app.v3.heavy_inbound_models import HeavyInboundInputs, HeavyInboundReceipt
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import TimedWorkload, WorkloadPolicy
from app.v3.workload_wire import workload_dict
from tests.v3.test_workload_fixtures import hand_source

PORTS = {
    "IN1": frozenset({"PALLET_LOAD", "HEAVY_BOX"}),
    "IN2": frozenset({"PALLET_LOAD", "HEAVY_BOX"}),
}


def _baseline(*, conflicting_initial_lot: bool = False) -> TimedWorkload:
    source = hand_source()
    pallet = replace(source.templates[0], archetype_id="PALLET_LOAD", gross_mass_kg=F(455))
    box = replace(source.templates[1], archetype_id="HEAVY_BOX", gross_mass_kg=F(10))
    if conflicting_initial_lot:
        box = replace(box, source_lot_id=pallet.source_lot_id)
    source = replace(source, templates=(pallet, box))
    return materialize_workload(source, WorkloadPolicy(8, 4, 2, "normal"))


def _receipt() -> HeavyInboundReceipt:
    return HeavyInboundReceipt("peer-job", "peer-HU", "peer-lot", "A", "IN1", 1)


def test_conflicting_initial_lot_definitions_cannot_be_silently_overwritten() -> None:
    before = _baseline(conflicting_initial_lot=True)
    # Two initial HUs have the same lot but distinct SKU/template definitions.
    assert before.source.templates[0].source_lot_id == before.source.templates[1].source_lot_id
    receipt = replace(_receipt(), sku_id="B", lot_id="initial-lot-A")
    with pytest.raises(ValueError, match=r"LOT.*CONFLICT"):
        augment_offers(before, (receipt,), PORTS)


def test_compatible_source_lot_is_not_mistaken_for_duplicate_physical_hu() -> None:
    before = _baseline()
    first = replace(_receipt(), lot_id="initial-lot-A")
    second = replace(first, job_id="peer-job-2", hu_id="peer-HU-2", arrival_tick=7)
    result = augment_offers(before, (second, first), PORTS)
    assert {r.offer.hu_id for r in result.receipts} == {"peer-HU", "peer-HU-2"}
    assert {r.offer.lot_id for r in result.receipts} == {"initial-lot-A"}
    assert result.deltas[0].added_mass_kg == F(910)
    assert len(result.postshift_jobs) == 8  # Original four inbound and two outbound plus two.


def test_additions_at_new_class_inlet_pairs_keep_all_old_quotas_and_arrivals() -> None:
    before = _baseline()
    raw = canonical_bytes(workload_dict(before))
    pallet = replace(_receipt(), port_id="IN2", arrival_tick=0)
    box = HeavyInboundReceipt("peer-box", "peer-box-HU", "peer-box-lot", "B", "IN1", 7)
    result = augment_offers(before, (pallet, box), PORTS)
    deltas = {(d.archetype_id, d.port_id): d for d in result.deltas}
    assert set(deltas) == {("PALLET_LOAD", "IN2"), ("HEAVY_BOX", "IN1")}
    assert all((d.before_count, d.added_count, d.after_count) == (0, 1, 1) for d in deltas.values())
    assert sum(d.added_mass_kg for d in deltas.values()) == F(465)
    remaining = tuple(
        j for j in result.postshift_jobs if j.job_id not in {pallet.job_id, box.job_id}
    )
    assert remaining == before.jobs
    assert canonical_bytes(workload_dict(before)) == raw
    assert (before.policy.inbound_hus, before.policy.outbound_hus) == (4, 2)


@pytest.mark.parametrize(
    "collision", ["new_job_as_hu", "new_hu_as_lot", "source_lot_as_job", "outbound_job_as_hu"]
)
def test_cross_field_identity_collisions_reject(collision: str) -> None:
    before = _baseline()
    first = _receipt()
    second = replace(first, job_id="peer-second", hu_id="peer-second-HU", lot_id="peer-second-lot")
    if collision == "new_job_as_hu":
        second = replace(second, hu_id=first.job_id)
    elif collision == "new_hu_as_lot":
        second = replace(second, lot_id=first.hu_id)
    elif collision == "source_lot_as_job":
        second = replace(second, job_id="initial-lot-A")
    else:
        second = replace(
            second, hu_id=next(j.job_id for j in before.jobs if j.direction == "outbound")
        )
    with pytest.raises(ValueError, match="IDENTITY"):
        augment_offers(before, (second, first), PORTS)


@pytest.fixture(scope="module")
def source_bound() -> HeavyInboundInputs:
    receipt = HeavyInboundReceipt(
        "peer-source-job", "peer-source-HU", "peer-source-lot", "DEMO_172", "IN_W_BULK", 1
    )
    return compile_heavy_inbound_inputs(WorkloadPolicy(60_000_000, 40, 60, "normal"), (receipt,))


class _Text(str):
    pass


@pytest.mark.parametrize("field", ["fingerprint_pair", "orientation"])
def test_retained_equal_container_and_text_aliases_reject(
    source_bound: HeavyInboundInputs, field: str
) -> None:
    value = source_bound
    if field == "fingerprint_pair":
        hashes = value.authority.raw_fingerprints
        wrong_hashes = (list(hashes[0]), *hashes[1:])
        authority = replace(value.authority, raw_fingerprints=wrong_hashes)  # type: ignore[arg-type]
        value = replace(value, authority=authority)
    else:
        first = value.receipts[0]
        template = replace(first.template, orientation_id=_Text(first.template.orientation_id))
        value = replace(value, receipts=(replace(first, template=template),))
    with pytest.raises(ValueError):
        verify_heavy_inbound_inputs(value)


def test_rehashed_old_arrival_change_in_both_views_still_rejects(
    source_bound: HeavyInboundInputs,
) -> None:
    wire = parse_json(source_bound.frozen_bytes)
    baseline = wire["authority"]["baseline"]
    original = baseline["jobs"][0]
    original["arrival_tick"] += 1
    counterpart = next(j for j in wire["postshift_jobs"] if j["job_id"] == original["job_id"])
    counterpart["arrival_tick"] = original["arrival_tick"]
    baseline["workload_id"] = sha256_hex({k: v for k, v in baseline.items() if k != "workload_id"})
    with pytest.raises(ValueError):
        load_heavy_inbound_inputs(canonical_bytes(wire))


@pytest.mark.parametrize("filename", ["baseline-assignment-v3.json", "cargo-catalog-v3.json"])
def test_fresh_raw_assignment_and_recipe_are_required(
    source_bound: HeavyInboundInputs, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    original = Path.read_bytes
    seen: list[str] = []

    def changed(path: Path) -> bytes:
        raw = original(path)
        if path.name == filename:
            seen.append(str(path))
            return raw + b" "
        return raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_heavy_inbound_inputs(source_bound)
    assert seen, "The fresh raw dependency must actually be read"
