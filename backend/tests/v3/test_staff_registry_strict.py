"""Exact nested types and raw pins remain authority after an initial valid compile."""

from dataclasses import replace
from pathlib import Path
from shutil import copyfile
from types import SimpleNamespace
from typing import Any

import pytest

from app.v3 import staff_registry
from app.v3.staff_registry import compile_staff_registry, require_same_registry
from app.v3.staff_registry_source import load_staff_source
from app.v3.staffing_analytical import analyze_staffing
from tests.v3.test_staff_registry_fixtures import SECOND, registry_document
from tests.v3.test_staffing_analytical import covers


@pytest.mark.parametrize(
    "path,value",
    [
        (("workers",), ()),
        (("workers", 0, "eligible_roles"), ("pick",)),
        (("workers", 0, "permitted_equipment"), "manual_cart"),
        (("workers", 0, "actor_id"), 1),
        (("workers", 0, "primary_role"), True),
        (("workers", 0, "eligible_roles"), ["pick", False]),
        (("workers", 0, "permitted_equipment"), ["manual_cart", "manual_cart"]),
        (("workers", 22, "permitted_equipment"), []),
        (("workers", 22, "permitted_equipment"), ["FL02"]),
        (("unavailability", 0, "reason"), " "),
        (("unavailability", 0, "end_tick"), True),
        (("station_bindings", 0, "station_id"), False),
    ],
)
def test_strict_nested_document_values(path: tuple[str | int, ...], value: Any) -> None:
    document = registry_document()
    target: Any = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        compile_staff_registry(document)


def test_retained_dataclass_bool_alias_does_not_inherit_valid_registry_identity() -> None:
    registry = compile_staff_registry(registry_document())
    assert len(registry.registry_common_hash) == 64
    object.__setattr__(registry.unavailability[0], "start_tick", False)
    with pytest.raises(ValueError, match="INTEGER_TICK"):
        _ = registry.registry_common_hash


def test_retained_nested_list_in_frozen_worker_is_rejected() -> None:
    registry = compile_staff_registry(registry_document())
    object.__setattr__(registry.workers[0], "eligible_roles", ["forklift"])
    with pytest.raises(ValueError, match="EXACT_TYPED_TUPLE"):
        analyze_staffing(registry, (), 0, SECOND)


def copy_staff_sources(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[2] / "data"
    paths = [
        "v3-proposal/provenance.json",
        "v3-conveyor-proposal/conveyor-v3.json",
        "v3-proposal/docs/v3/contract-proposals/port-resource-policy-v3.json",
        "v3-proposal/docs/v3/contract-proposals/layout-links-v3.json",
    ]
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(root / path, target)
    return tmp_path


@pytest.mark.parametrize(
    "relative",
    [
        "v3-proposal/provenance.json",
        "v3-conveyor-proposal/conveyor-v3.json",
        "v3-proposal/docs/v3/contract-proposals/port-resource-policy-v3.json",
        "v3-proposal/docs/v3/contract-proposals/layout-links-v3.json",
    ],
)
def test_retained_registry_rechecks_raw_source_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    root = copy_staff_sources(tmp_path)
    monkeypatch.setattr(staff_registry, "load_staff_source", lambda: load_staff_source(root))
    registry = compile_staff_registry(registry_document())
    assert len(registry.registry_common_hash) == 64
    target = root / relative
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="MISMATCH"):
        _ = registry.registry_common_hash


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_tick", True),
        ("end_tick", 160.0),
        ("outward_ticks", False),
        ("return_ticks", 0),
        ("return_ticks", -1),
        ("outward_ticks", 60 * SECOND),
        ("start_tick", 160 * SECOND),
    ],
)
def test_analytical_cover_strict_periods(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        replace(covers()[0], **{field: value})


@pytest.mark.parametrize("start,end", [(False, 0), (0, True), (0.0, 1), (1, 0), (-1, 0)])
def test_analyzer_strict_observation_window(start: Any, end: Any) -> None:
    with pytest.raises(ValueError):
        analyze_staffing(compile_staff_registry(registry_document()), (), start, end)


def test_caller_claimed_canonical_bytes_are_not_registry_equality_proof() -> None:
    registry = compile_staff_registry(registry_document())
    forged: Any = SimpleNamespace(canonical_bytes=registry.canonical_bytes)
    with pytest.raises(ValueError, match="STAFF_REGISTRY_TYPE_REQUIRED"):
        require_same_registry(forged, registry)


def test_missing_pinned_source_has_explicit_registry_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="STAFF_SOURCE_UNAVAILABLE"):
        load_staff_source(tmp_path)
