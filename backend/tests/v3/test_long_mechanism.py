"""Small metadata/authority doubles: no source-world compilation or triangle processing."""

import json
import struct
from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.v3.adaptation_authority import require_same_authority
from app.v3.input_models import HandlingUnit
from app.v3.long_freight_models import (
    LongFreightAuthority,
    LongFreightRequirements,
    LongFreightStatic,
)
from app.v3.long_mechanism_interlock import check_long_mechanism
from app.v3.long_mechanism_models import JointValue, LongMechanismInterface, LongMechanismState
from app.v3.long_mechanism_source import load_long_mechanism_interface
from app.v3.workload_models import TimedWorkload, WorkloadPolicy, WorkloadSource
from tests.v3.test_long_freight_inputs import request


def requirements() -> LongFreightRequirements:
    source = WorkloadSource("hand", "layout", (), (), (), (), ())
    workload = TimedWorkload(source, WorkloadPolicy(1, 0, 0, "normal"), (), (), (), "p", "w")
    req = request()
    hu = HandlingUnit(
        req.hu_id,
        "DEMO_180",
        "LONG_BUNDLE",
        "lot",
        req.source_slot_id,
        "LONG_W:002",
        24,
        200.0,
        "upright_xyz",
    )
    authority = LongFreightAuthority("hand", "layout", (), b"{}", b"{}", (hu,), workload, b"{}")
    static = LongFreightStatic(
        "prerequisites_only",
        (),
        (F(4), F(1), F(1)),
        (F(5), F(1), F(1)),
        F(200),
        F(40),
        F(240),
        F(6),
        F(4),
        F(210),
        True,
        True,
    )
    return LongFreightRequirements(req, authority, static, (), b"hand-requirements", "hand-id")


def glb(nodes: list[dict[str, Any]]) -> bytes:
    raw = json.dumps({"nodes": nodes}).encode()
    raw += b" " * (-len(raw) % 4)
    return (
        struct.pack("<4sII", b"glTF", 2, 28 + len(raw))
        + struct.pack("<II", len(raw), 0x4E4F534A)
        + raw
        + struct.pack("<II", 0, 0x004E4942)
    )


def joint(name: str, axis: str, low: float, high: float, rotation: bool = False) -> dict[str, Any]:
    prefix = "rotation_delta_range_deg" if rotation else "translation_delta_range_m"
    return {
        "name": name,
        "extras": {
            prefix: [low, high],
            "rotation_axis_runtime" if rotation else "translation_axis_runtime": axis,
            "bind_local_runtime": [0, 0, 0],
            "requires_stopped_handling": True,
        },
    }


def hand_files() -> dict[str, bytes]:
    base = [joint("joint__cradle_lock_" + s, "Y", 0, 0.11) for s in ("L", "R")]
    rig = [
        joint(
            "joint__restraint_keeper_" + s + "_" + p,
            "X",
            -0.35 if s == "L" else 0,
            0.35 if s == "R" else 0,
        )
        for s in ("L", "R")
        for p in ("front", "rear")
    ]
    rig += [joint("joint__restraint_" + s, "X", -80, 0, True) for s in ("L", "R")]
    geo: dict[str, Any] = {
        "loaded": {
            "mass_kg": {"HU": 200, "attachment_total_including_upper_rig": 40, "loaded": 240},
            "actual_zero_gap_lower_supports": [[0, 0.15, 0]],
            "actual_zero_gap_top_restraints": [[0, 0.592, 0]],
            "actions_accepted": False,
        }
    }
    files = {"base.glb": glb(base), "upper.glb": glb(rig), "loaded.glb": glb([])}
    geo.update(
        {
            k: sha256(files[p]).hexdigest()
            for k, p in [
                ("base_glb_sha256", "base.glb"),
                ("upper_rig_glb_sha256", "upper.glb"),
                ("loaded_fixture_glb_sha256", "loaded.glb"),
            ]
        }
    )
    files["geometry.json"] = json.dumps(geo).encode() + b"\n"
    files["c08.json"] = (
        b'{"schema_version":"0.2.0","loads":'
        b'[{"archetype_id":"LONG_BUNDLE","fork_top_travel_y_m":0.75}]}\n'
    )
    return files


@pytest.fixture
def bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LongMechanismInterface:
    from app.v3 import long_mechanism_source as source

    files = hand_files()
    names = {
        "geometry": "geometry.json",
        "base": "base.glb",
        "upper": "upper.glb",
        "loaded": "loaded.glb",
        "c08": "c08.json",
    }
    pins = tuple(
        (key, path, sha256(files[path]).hexdigest(), path.endswith(".json"))
        for key, path in names.items()
    )
    monkeypatch.setattr(source, "PINS", pins)
    expected = requirements()

    def verify(value: LongFreightRequirements) -> LongFreightRequirements:
        require_same_authority(value, expected)
        return requirements()

    monkeypatch.setattr(source, "verify_long_freight_requirements", verify)
    for path, raw in files.items():
        (tmp_path / path).write_bytes(raw)
    return load_long_mechanism_interface(tmp_path, expected)


def state(interface: LongMechanismInterface) -> LongMechanismState:
    return LongMechanismState(
        request().hu_id,
        "lot",
        "v3:attachment:long-cradle:01",
        "F02",
        "FL02",
        "vehicle:FL02",
        "mounted",
        None,
        tuple(JointValue(j.node_id, F(0)) for j in interface.joints),
        F(0),
        F(0),
        F(3, 4),
        True,
    )


def test_closed_loaded_state_is_only_a_mechanical_prerequisite(
    bound: LongMechanismInterface,
) -> None:
    before = state(bound)
    result = check_long_mechanism(bound, before, "loaded_transit")
    assert result.mechanically_ready and result.reasons == ()
    assert result.operational_admission is False and result.full_n3_acceptance is False
    assert before == state(bound)
    assert bound.hu_mass_kg == F(200) and bound.attachment_mass_kg == F(40)
    assert bound.total_lifted_kg == F(240) and bound.component_mass_split is None


@pytest.mark.parametrize("index", range(8))
def test_each_independent_open_joint_blocks_travel(
    bound: LongMechanismInterface, index: int
) -> None:
    before = state(bound)
    definition = bound.joints[index]
    opened = definition.minimum if definition.minimum else definition.maximum
    joints = tuple(
        replace(j, value=opened) if i == index else j for i, j in enumerate(before.joints)
    )
    result = check_long_mechanism(bound, replace(before, joints=joints), "loaded_transit")
    assert not result.mechanically_ready
    assert "LONG_JOINT_NOT_CLOSED" in result.reasons


def test_empty_and_asserted_stow_never_grant_missing_fixture(bound: LongMechanismInterface) -> None:
    result = check_long_mechanism(bound, state(bound), "empty_cradle_transit")
    assert "UPPER_RIG_MUST_BE_STOWED" in result.reasons
    value = replace(
        state(bound),
        hu_id=None,
        lot_id=None,
        upper_rig_location="stowed",
        declared_stow_id="invented",
    )
    result = check_long_mechanism(bound, value, "empty_cradle_transit")
    assert result.reasons == ("STOW_AUTHORITY_MISSING",)
    assert not result.mechanically_ready


def test_joint_adjustment_requires_stopped_state(bound: LongMechanismInterface) -> None:
    assert check_long_mechanism(bound, state(bound), "joint_adjustment").mechanically_ready
    result = check_long_mechanism(bound, replace(state(bound), stopped=False), "joint_adjustment")
    assert result.reasons == ("STOPPED_HANDLING_REQUIRED",)


@pytest.mark.parametrize(
    "field,value",
    [
        ("vehicle_id", "FL01"),
        ("actor_id", "F01"),
        ("custody_owner", "slot:elsewhere"),
        ("hu_id", "clone"),
        ("lot_id", "wrong"),
        ("attachment_id", "second-cradle"),
        ("relative_yaw_rad", 0.0),
        ("reach_m", False),
        ("stopped", 1),
    ],
)
def test_identity_custody_and_equal_value_aliases_reject(
    bound: LongMechanismInterface, field: str, value: Any
) -> None:
    with pytest.raises(ValueError):
        check_long_mechanism(bound, replace(state(bound), **{field: value}), "loaded_transit")


def test_retained_interface_and_rehashed_source_changes_reject(
    bound: LongMechanismInterface,
) -> None:
    with pytest.raises(ValueError):
        check_long_mechanism(replace(bound, total_lifted_kg=F(241)), state(bound), "loaded_transit")
    doc = bound.documents[0]
    altered = replace(doc, raw=doc.raw + b" ", raw_sha256=sha256(doc.raw + b" ").hexdigest())
    with pytest.raises(ValueError):
        check_long_mechanism(
            replace(bound, documents=(altered, *bound.documents[1:])),
            state(bound),
            "loaded_transit",
        )


@pytest.mark.parametrize("value", [False, 0, 0.0])
def test_joint_numerical_aliases_reject(bound: LongMechanismInterface, value: Any) -> None:
    before = state(bound)
    joints = (replace(before.joints[0], value=value), *before.joints[1:])
    with pytest.raises(ValueError):
        check_long_mechanism(bound, replace(before, joints=joints), "loaded_transit")


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "missing", "outside"])
def test_joint_universe_and_range(bound: LongMechanismInterface, mutation: str) -> None:
    before = state(bound)
    joints = list(before.joints)
    if mutation == "unknown":
        joints[0] = replace(joints[0], node_id="invented")
    elif mutation == "duplicate":
        joints[1] = joints[0]
    elif mutation == "missing":
        joints.pop()
    else:
        joints[0] = replace(joints[0], value=bound.joints[0].maximum + F(1, 1000))
    with pytest.raises(ValueError):
        check_long_mechanism(bound, replace(before, joints=tuple(joints)), "loaded_transit")


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("relative_yaw_rad", F(1), "LONG_RELATIVE_YAW_FORBIDDEN"),
        ("reach_m", F(2, 5), "LONG_TRAVEL_POSE_REQUIRED"),
        ("fork_top_m", F(1, 5), "LONG_TRAVEL_POSE_REQUIRED"),
        ("upper_rig_location", "unlocated", "UPPER_RIG_NOT_MOUNTED"),
    ],
)
def test_source_travel_prerequisites(
    bound: LongMechanismInterface, field: str, value: Any, reason: str
) -> None:
    result = check_long_mechanism(bound, replace(state(bound), **{field: value}), "loaded_transit")
    assert not result.mechanically_ready and reason in result.reasons


def test_upstream_requirements_are_reverified_each_call(
    bound: LongMechanismInterface, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.v3 import long_mechanism_source as source

    def denied(value: LongFreightRequirements) -> LongFreightRequirements:
        raise ValueError("fresh upstream authority denied")

    monkeypatch.setattr(source, "verify_long_freight_requirements", denied)
    with pytest.raises(ValueError, match="fresh upstream"):
        check_long_mechanism(bound, state(bound), "loaded_transit")


def test_text_newlines_are_portable_but_raw_provenance_is_retained(
    bound: LongMechanismInterface, tmp_path: Path
) -> None:
    first = bound.documents[0]
    (tmp_path / first.path).write_bytes(first.raw.replace(b"\n", b"\r\n"))
    other = load_long_mechanism_interface(tmp_path, requirements())
    assert other.joints == bound.joints and other.lower_contacts_m == bound.lower_contacts_m
    assert other.documents[0].normalized_text_sha256 == first.normalized_text_sha256
    assert other.documents[0].raw_sha256 != first.raw_sha256
    assert other.input_hash != bound.input_hash


def test_disk_corruption_and_missing_assets_fail_closed(
    bound: LongMechanismInterface, tmp_path: Path
) -> None:
    path = tmp_path / bound.documents[1].path
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="fingerprint"):
        load_long_mechanism_interface(tmp_path, requirements())
    path.unlink()
    with pytest.raises(ValueError, match="Missing"):
        load_long_mechanism_interface(tmp_path, requirements())


def test_unknown_joint_in_authenticated_metadata_double_rejects(
    bound: LongMechanismInterface, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.v3 import long_mechanism_source as source

    raw = glb([joint("joint__unknown", "Y", 0, 0.11)])
    path = tmp_path / "base.glb"
    path.write_bytes(raw)
    geometry = json.loads((tmp_path / "geometry.json").read_bytes())
    geometry["base_glb_sha256"] = sha256(raw).hexdigest()
    (tmp_path / "geometry.json").write_bytes(json.dumps(geometry).encode())
    pins = tuple(
        (role, name, sha256((tmp_path / name).read_bytes()).hexdigest(), text)
        for role, name, _, text in source.PINS
    )
    monkeypatch.setattr(source, "PINS", pins)
    with pytest.raises(ValueError, match="eight"):
        load_long_mechanism_interface(tmp_path, requirements())


def test_retained_joint_pivot_and_type_alias_do_not_inherit_authority(
    bound: LongMechanismInterface,
) -> None:
    altered = replace(bound.joints[0], declared_pivot_m=(F(1), F(0), F(0)))
    with pytest.raises(ValueError):
        check_long_mechanism(
            replace(bound, joints=(altered, *bound.joints[1:])), state(bound), "loaded_transit"
        )
    alias: Any = 200
    with pytest.raises(ValueError):
        check_long_mechanism(replace(bound, hu_mass_kg=alias), state(bound), "loaded_transit")


def test_unknown_mode_and_repeated_noop_state(bound: LongMechanismInterface) -> None:
    value: Any = "pickup_and_credit"
    with pytest.raises(ValueError, match="mode"):
        check_long_mechanism(bound, state(bound), value)
    first = check_long_mechanism(bound, state(bound), "loaded_transit")
    second = check_long_mechanism(bound, state(bound), "loaded_transit")
    assert first == second
