"""Retained analytical records and returned source projections grant no unchecked authority."""

from pathlib import Path

import pytest

from app.v3 import staff_registry
from app.v3.staff_registry import compile_staff_registry
from app.v3.staff_registry_source import load_staff_source
from app.v3.staffing_analytical import analyze_staffing
from app.v3.staffing_identity import analytical_allocation_hash
from app.v3.staffing_models import AnalyticalCover
from tests.v3.test_staff_independent_boundaries import _document
from tests.v3.test_staff_registry_strict import copy_staff_sources


def test_retained_cover_numeric_alias_rechecks_before_hash_or_analysis() -> None:
    registry = compile_staff_registry(_document())
    cover = AnalyticalCover("C", "P11", "PK05", 10, 20, 1, 3)
    assert len(analytical_allocation_hash(registry, (cover,))) == 64
    object.__setattr__(cover, "outward_ticks", True)
    assert cover.outward_ticks == 1
    with pytest.raises(ValueError, match="INTEGER_TICK_REQUIRED"):
        analytical_allocation_hash(registry, (cover,))
    with pytest.raises(ValueError, match="INTEGER_TICK_REQUIRED"):
        analyze_staffing(registry, (cover,), 10, 20)


def test_returned_source_projection_cannot_replace_fresh_pinned_authority() -> None:
    registry = compile_staff_registry(_document())
    before = registry.canonical_bytes
    exposed = registry.source
    original_station = exposed.stations[0]
    object.__setattr__(exposed, "actor_ids", ("P13",))
    object.__setattr__(original_station, "service_node_id", "invented:service")
    fresh = registry.source
    assert len(fresh.actor_ids) == 24 and "P13" not in fresh.actor_ids
    assert fresh.stations[0].service_node_id == "v3:service:PK01"
    assert registry.canonical_bytes == before
    assert analyze_staffing(registry, (), 0, 1).roster_person_ticks == 24


def test_same_size_source_substitution_rejects_after_valid_common_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_staff_sources(tmp_path)
    monkeypatch.setattr(staff_registry, "load_staff_source", lambda: load_staff_source(root))
    registry = compile_staff_registry(_document())
    assert len(registry.registry_common_hash) == 64
    path = root / "v3-proposal/docs/v3/contract-proposals/port-resource-policy-v3.json"
    original = path.read_bytes()
    changed = original.replace(b'"P01"', b'"P13"', 1)
    assert len(changed) == len(original) and changed != original
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="STAFF_SOURCE_BYTES_MISMATCH"):
        analyze_staffing(registry, (), 0, 1)
