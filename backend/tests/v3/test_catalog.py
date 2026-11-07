"""Source-labelled V3 catalog and stock pose expectations come from manual arithmetic."""

import copy

import pytest

from app.v3.catalog import build_catalog, build_initial_state
from tests.v3.test_interface_sources import small_bundle


def test_catalog_is_static_separates_identities_and_does_not_claim_execution() -> None:
    bundle = small_bundle()
    result = build_catalog(bundle)
    assert result["schema_id"] == "qoima.catalog.v3-proposal"
    assert result["layout"]["bounds"]["max"] == [144, 8, 72]
    assert result["capabilities"]["actual_engine_run"] is False
    assert result["capabilities"]["operational_admission"] is False
    assert result["counts"] == {
        "skus": 1,
        "archetypes": 1,
        "slots": 2,
        "modules": 1,
        "ports": 2,
        "actors": 2,
        "handling_units": 2,
    }
    assert result["asset_archetypes"][0]["binding_status"] == "not_bound"
    assert all("initial_pos" not in actor and "role" not in actor for actor in result["actors"])
    result["skus"][0]["sku_id"] = "CHANGED"
    assert build_catalog(bundle)["skus"][0]["sku_id"] == "DEMO_001"


def test_initial_hu_floor_pose_uses_v3_module_yaw_without_duplicate_lot_stock() -> None:
    bundle = small_bundle()
    result = build_initial_state(bundle)
    assert result["totals"] == {
        "handling_units": 2,
        "occupied_slots": 2,
        "quantity_units": 4,
        "gross_mass_kg": 5.0,
    }
    first, second = result["handling_units"]
    assert first["pose"]["world_pos"] == pytest.approx([10.2, 0.5, 19])
    assert second["pose"]["world_pos"] == pytest.approx([10.2, 0.5, 18])
    assert first["pose"]["origin"] == "floor_centre_XZ_Y0"
    assert first["lot_id"] == second["lot_id"] == "LOT1"
    assert result["inventory_by_sku"] == [{"sku_id": "DEMO_001", "quantity_units": 4}]
    assert "events" not in result and "metrics" not in result
    before = copy.deepcopy(result)
    build_catalog(bundle)
    assert result == before
