"""Contract loading, schema validation and semantic layout checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle, ContractError, load_contract_bundle
from app.contracts.validation import validate_bundle, validate_layout


def _raw_layout(contracts_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (contracts_dir / "layout.example.json").read_text(encoding="utf-8")
    )
    return data


def test_bundle_loads_all_contract_files(bundle: ContractBundle) -> None:
    assert bundle.layout.layout_version == "qoima-72x48-v2"
    assert bundle.config.layout_version == bundle.layout.layout_version
    assert len(bundle.actors.actors) == 24
    assert len(bundle.actors.vehicles) == 2


def test_repository_contracts_pass_semantic_validation(bundle: ContractBundle) -> None:
    assert validate_bundle(bundle) == []


def test_layout_rejects_unknown_fields(contracts_dir: Path) -> None:
    raw = _raw_layout(contracts_dir)
    raw["unexpected"] = 1
    with pytest.raises(ValidationError):
        Layout.from_data(raw)


def test_layout_rejects_nan(contracts_dir: Path) -> None:
    raw = _raw_layout(contracts_dir)
    raw["picker_graph"]["edges"][0]["length_m"] = float("nan")
    with pytest.raises(ValidationError):
        Layout.from_data(raw)


def test_layout_is_immutable(layout: Layout) -> None:
    with pytest.raises(ValidationError):
        layout.layout_version = "other"  # type: ignore[misc]


def test_semantic_check_detects_wrong_edge_length(contracts_dir: Path) -> None:
    raw = copy.deepcopy(_raw_layout(contracts_dir))
    raw["picker_graph"]["edges"][0]["length_m"] = 3.0
    issues = validate_layout(Layout.from_data(raw))
    assert any("edge length" in issue for issue in issues)


def test_semantic_check_detects_edge_through_rack(contracts_dir: Path) -> None:
    raw = copy.deepcopy(_raw_layout(contracts_dir))
    raw["picker_graph"]["edges"].append({"a": "N_A01_Z16", "b": "N_A02_Z16", "length_m": 4.5})
    issues = validate_layout(Layout.from_data(raw))
    assert any("crosses rack" in issue for issue in issues)


def test_semantic_check_detects_reserve_with_walk_access(contracts_dir: Path) -> None:
    raw = copy.deepcopy(_raw_layout(contracts_dir))
    reserve = next(s for s in raw["slots"] if s["kind"] == "reserve")
    reserve["service_node_id"] = "N_A01_Z16"
    issues = validate_layout(Layout.from_data(raw))
    assert any("reserve slot" in issue for issue in issues)


def test_loader_reports_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ContractError):
        load_contract_bundle(tmp_path / "missing")


def test_loader_reports_schema_violation(tmp_path: Path, contracts_dir: Path) -> None:
    for name in contracts_dir.glob("*.json"):
        (tmp_path / name.name).write_bytes(name.read_bytes())
    raw = _raw_layout(contracts_dir)
    raw["schema_version"] = "1.0"
    (tmp_path / "layout.example.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ContractError, match=r"layout\.example\.json"):
        load_contract_bundle(tmp_path)
