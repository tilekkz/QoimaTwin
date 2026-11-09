"""Fresh exact source bytes and upstream requirements; no triangle decoding or source grants."""

from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.long_freight_binding import verify_long_freight_requirements
from app.v3.long_freight_models import LongFreightRequirements
from app.v3.long_mechanism_models import (
    ASSET_REVISION,
    VERSION,
    XYZ,
    JointDefinition,
    LongMechanismInterface,
    MechanismDocument,
)
from app.v3.mesh_proof_glb import _chunks
from app.v3.pallet_outbound_pickup_identity import identity, require

PINS = (
    (
        "geometry",
        "assets/v3/specs/long-cradle.geometry.json",
        "2f58bb1b40f20e75f77b98917d24fb58c7aeb93480972e08e99c4283279ca27a",
        True,
    ),
    (
        "base",
        "frontend/public/models/v3/long-cradle.glb",
        "5fc1251b9408ad0b942f413412e04b60ef90ad36b57564365ba8e7e27d93c8ed",
        False,
    ),
    (
        "upper",
        "frontend/public/models/v3/long-restraint-rig.glb",
        "49f997146d9fe09b9caba276eb1db30124f71c59a8aa559df67b18dc1c1486d8",
        False,
    ),
    (
        "loaded",
        "frontend/public/models/v3/long-cradle-loaded-fixture.glb",
        "737db9a931626b8554db15c8c1f71cc3dd5ce4628b301976aea26a6cc7497758",
        False,
    ),
    (
        "c08",
        "docs/v3/contract-proposals/vehicle-handling-v3.json",
        "22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4",
        True,
    ),
)


def _document(role: str, path: str, raw: bytes, digest: str, text: bool) -> MechanismDocument:
    require(type(raw) is bytes, "Exact mechanism raw bytes required")
    normalized = raw
    if text:
        decoded = raw.decode("utf-8").replace("\r\n", "\n")
        require("\r" not in decoded, "Only LF/CRLF source text supported")
        normalized = decoded.encode("utf-8")
    require(sha256(normalized).hexdigest() == digest, "Mechanism source fingerprint changed")
    return MechanismDocument(role, path, raw, sha256(raw).hexdigest(), digest if text else None)


def _documents(values: tuple[MechanismDocument, ...]) -> tuple[MechanismDocument, ...]:
    require(type(values) is tuple and len(values) == len(PINS), "Closed mechanism document set")
    result = []
    for value, (role, path, digest, text) in zip(values, PINS, strict=True):
        require(type(value) is MechanismDocument, "Exact mechanism document required")
        expected = _document(role, path, value.raw, digest, text)
        require_same_authority(value, expected)
        result.append(expected)
    return tuple(result)


def _number(value: Any) -> F:
    require(type(value) in (int, float), "Exact finite source number required")
    return F(str(value))


def _xyz(value: Any) -> XYZ:
    require(type(value) is list and len(value) == 3, "Exact source XYZ required")
    return _number(value[0]), _number(value[1]), _number(value[2])


def _joint(node: dict[str, Any], component: str) -> JointDefinition:
    data = node["extras"]
    rotation = "rotation_delta_range_deg" in data
    motion = "rotation_deg" if rotation else "translation_m"
    key = "rotation_delta_range_deg" if rotation else "translation_delta_range_m"
    axis = data["rotation_axis_runtime" if rotation else "translation_axis_runtime"]
    require(type(axis) is str and axis in {"X", "Y"}, "Unknown mechanism joint axis")
    require(
        data.get("requires_stopped_handling", data.get("open_requires_stop")) is True,
        "Source joint stopped interlock required",
    )
    low, high = (_number(v) for v in data[key])
    require(low <= 0 <= high and low < high, "Closed-zero source joint range required")
    return JointDefinition(
        node["name"],
        component,
        axis,
        motion,
        low,
        high,
        _xyz(data["bind_local_runtime"]),
        _xyz(node.get("translation", [0, 0, 0])),
    )


def _joints(raws: dict[str, bytes]) -> tuple[JointDefinition, ...]:
    expected = {"joint__cradle_lock_" + s for s in ("L", "R")}
    expected |= {"joint__restraint_" + s for s in ("L", "R")}
    expected |= {
        "joint__restraint_keeper_" + s + "_" + p for s in ("L", "R") for p in ("front", "rear")
    }
    result = []
    for component in ("base", "upper"):
        document, _ = _chunks(raws[component])
        for node in document["nodes"]:
            if node.get("name", "").startswith("joint__"):
                result.append(_joint(node, component))
    require(
        len(result) == 8 and {j.node_id for j in result} == expected,
        "Exact eight source mechanism joints required",
    )
    return tuple(sorted(result, key=lambda j: j.node_id))


def _geometry(raws: dict[str, bytes]) -> dict[str, Any]:
    geometry: dict[str, Any] = parse_json(raws["geometry"])
    for role, key in (
        ("base", "base_glb_sha256"),
        ("upper", "upper_rig_glb_sha256"),
        ("loaded", "loaded_fixture_glb_sha256"),
    ):
        require(geometry[key] == sha256(raws[role]).hexdigest(), "Geometry/GLB binding differs")
    require(geometry["loaded"]["actions_accepted"] is False, "Geometry is not action authority")
    return geometry


def _build(
    documents: tuple[MechanismDocument, ...], requirements: LongFreightRequirements
) -> LongMechanismInterface:
    documents = _documents(documents)
    verified = verify_long_freight_requirements(requirements)
    require(
        verified.static.status == "prerequisites_only" and not verified.static.reasons,
        "Statically rejected LONG request cannot bind a mechanism",
    )
    raws = {d.role: d.raw for d in documents}
    loaded = _geometry(raws)["loaded"]
    masses = loaded["mass_kg"]
    hu = _number(masses["HU"])
    attachment = _number(masses["attachment_total_including_upper_rig"])
    total = _number(masses["loaded"])
    require(
        (hu, attachment, total)
        == (
            verified.static.hu_mass_kg,
            verified.static.attachment_mass_kg,
            verified.static.total_lifted_kg,
        )
        and hu + attachment == total,
        "Source LONG mass authority differs",
    )
    c08 = parse_json(raws["c08"])
    load = next(row for row in c08["loads"] if row["archetype_id"] == "LONG_BUNDLE")
    result = LongMechanismInterface(
        verified,
        documents,
        _joints(raws),
        tuple(_xyz(p) for p in loaded["actual_zero_gap_lower_supports"]),
        tuple(_xyz(p) for p in loaded["actual_zero_gap_top_restraints"]),
        hu,
        attachment,
        total,
        _number(load["fork_top_travel_y_m"]),
        None,
        ASSET_REVISION,
        VERSION,
        "",
    )
    return replace(result, input_hash=identity(result))


def load_long_mechanism_interface(
    asset_root: Path, requirements: LongFreightRequirements
) -> LongMechanismInterface:
    """Explicit source tree required. Original bytes retained; no personal-path fallback."""
    try:
        docs = tuple(
            _document(role, path, (asset_root / path).read_bytes(), digest, text)
            for role, path, digest, text in PINS
        )
        return _build(docs, requirements)
    except (OSError, UnicodeError, KeyError, StopIteration, TypeError) as error:
        raise ValueError("Missing or malformed LONG mechanism source") from error


def verify_long_mechanism_interface(value: LongMechanismInterface) -> LongMechanismInterface:
    require(type(value) is LongMechanismInterface, "Exact LONG mechanism interface required")
    expected = _build(value.documents, value.requirements)
    require_same_authority(value, expected)
    return expected
