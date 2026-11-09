"""Independent N3 namespace, balanced-mass tampering and retained-authority probes."""

from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.long_freight_binding import (
    compile_long_freight_requirements,
    load_long_freight_requirements,
    verify_long_freight_requirements,
)
from app.v3.long_freight_checks import straight_gate_fits
from app.v3.long_freight_models import LongFreightRequirements
from tests.v3.test_long_freight_inputs import policy, request


@pytest.fixture(scope="module")
def source_bound() -> LongFreightRequirements:
    return compile_long_freight_requirements(request(), policy())


def test_long_workload_mass_and_axes_are_c10_cargo_facts(
    source_bound: LongFreightRequirements,
) -> None:
    source = source_bound.authority.workload.source
    template = next(row for row in source.templates if row.sku_id == "DEMO_180")
    # C02 24 packaged units at8kg +8kg HU tare; C08 40kg attachment is separate.
    assert template.gross_mass_kg == F(24 * 8 + 8) == F(200)
    assert template.dimensions_xyz_m == (F("4.2"), F(".52"), F(".65"))
    assert template.orientation_id == "upright_xyz"
    assert [(r.port_id, r.weight) for r in source.inbound_weights if r.sku_id == "DEMO_180"] == [
        ("IN_W_BULK", F(2)),
    ]
    assert [(r.port_id, r.weight) for r in source.outbound_weights if r.sku_id == "DEMO_180"] == [
        ("OUT_E_B2B", F(2)),
    ]
    assert source_bound.static.attachment_mass_kg == F(40)


@pytest.mark.parametrize(
    "change", ["fingerprint_inner_list", "source_hu_mass_int", "design_bool_int"]
)
def test_equal_retained_nested_aliases_never_inherit_source_authority(
    source_bound: LongFreightRequirements,
    change: str,
) -> None:
    authority = source_bound.authority
    if change == "fingerprint_inner_list":
        rows: Any = (list(authority.raw_fingerprints[0]), *authority.raw_fingerprints[1:])
        altered = replace(source_bound, authority=replace(authority, raw_fingerprints=rows))
    elif change == "source_hu_mass_int":
        original = next(h for h in authority.initial_hus if h.handling_unit_id == request().hu_id)
        assert type(original.gross_mass_kg) is float and original.gross_mass_kg == 200
        hus = tuple(
            replace(h, gross_mass_kg=200) if h is original else h for h in authority.initial_hus
        )
        altered = replace(source_bound, authority=replace(authority, initial_hus=hus))
    else:
        value: Any = 1
        altered = replace(
            source_bound, static=replace(source_bound.static, pickup_design_passed=value)
        )
    with pytest.raises(ValueError):
        verify_long_freight_requirements(altered)


@pytest.mark.parametrize("change", ["mass_partition", "signed_frame_obligation", "extra_yaw_field"])
def test_rehashed_consistent_totals_or_extra_frame_do_not_create_grants(
    source_bound: LongFreightRequirements,
    change: str,
) -> None:
    wire = parse_json(source_bound.frozen_bytes)
    if change == "mass_partition":
        wire["static"]["hu_mass_kg"] = {"numerator": 240, "denominator": 1}
        wire["static"]["attachment_mass_kg"] = {"numerator": 0, "denominator": 1}
        assert wire["static"]["total_lifted_kg"] == {"numerator": 240, "denominator": 1}
    elif change == "signed_frame_obligation":
        row = next(r for r in wire["blockers"] if r["code"] == "LOADED_ROUTE_GATE_SWEEP_REQUIRED")
        row["required_fields"].remove("signed_HU_vehicle_orientation")
        assert len(wire["blockers"]) == 7 and row["required_fields"]
    else:
        wire["request"]["relative_yaw_rad"] = 0
    raw = canonical_bytes(wire)
    with pytest.raises(ValueError):
        load_long_freight_requirements(raw)
    with pytest.raises(ValueError):
        verify_long_freight_requirements(
            replace(source_bound, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())
        )


@pytest.mark.parametrize(
    "basename", ["baseline-input-v3.json", "baseline-assignment-v3.json", "vehicle-graph-v3.json"]
)
def test_fresh_verification_reauthenticates_independent_raw_packages(
    source_bound: LongFreightRequirements,
    monkeypatch: pytest.MonkeyPatch,
    basename: str,
) -> None:
    read = Path.read_bytes
    touched = []

    def changed(path: Path) -> bytes:
        raw = read(path)
        if path.name == basename:
            touched.append(path)
            return raw + b" "
        return raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_long_freight_requirements(source_bound)
    assert touched


@pytest.mark.parametrize(
    "change,reason",
    [
        (
            {
                "port_id": "IN_W_BULK",
                "pair_id": "INBOUND_FORKLIFT_PAIR",
                "actor_id": "F01",
                "vehicle_id": "FL01",
            },
            "FIXED_OUTBOUND_PAIR_REQUIRED",
        ),
        ({"orientation_id": "upright_xyz_in_module"}, "ORIENTATION_FORBIDDEN"),
    ],
)
def test_adjacent_valid_namespaces_do_not_become_an_outbound_cargo_frame(
    change: dict[str, str],
    reason: str,
) -> None:
    result = compile_long_freight_requirements(replace(request(), **change), policy())
    assert result.static.status == "static_rejected" and reason in result.static.reasons
    assert result.operational_admission is False and result.full_n3_acceptance is False
    assert len(result.blockers) == 7


def test_straight_gate_does_not_rotate_long_width_into_gate_height() -> None:
    assert not straight_gate_fits((F("4.2"), F("1.32")), (F(3), F(6)), F(0))


def test_gate_container_subclass_is_not_an_exact_measurement() -> None:
    class AliasTuple(tuple[F, F]):
        pass

    with pytest.raises(ValueError):
        straight_gate_fits(AliasTuple((F("4.2"), F("1.32"))), (F(6), F(3)), F(0))
