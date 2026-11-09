"""Real pinned V3 stock projected through the agreed immutable ingestion seam."""

from decimal import localcontext
from pathlib import Path

import pytest

from app.v3.export import build_static_export
from app.v3.inputs import load_v3_bundle


def test_actual_pinned_bundle_projects_530_hus_without_v2_defaults() -> None:
    bundle = load_v3_bundle(Path(__file__).parents[2] / "data/v3-proposal")
    value = build_static_export(bundle)
    catalog, state = value["catalog"], value["initial_state"]
    assert catalog["counts"] == {
        "skus": 200,
        "archetypes": 8,
        "slots": 776,
        "modules": 132,
        "ports": 6,
        "actors": 24,
        "handling_units": 530,
    }
    assert state["totals"] == {
        "handling_units": 530,
        "occupied_slots": 530,
        "quantity_units": 12256,
        "gross_mass_kg": 9403.85,
    }
    first = state["handling_units"][0]
    assert first["handling_unit_id"] == "v3:HU:initial:DEMO_001:01"
    # module origin126/51.4, yawpi/2, local centre.88/.30 ->126.30/50.52; floorY=.25.
    assert first["pose"]["world_pos"] == pytest.approx([126.3, 0.25, 50.52])
    assert catalog["layout"]["bounds"]["max"] == [144, 8, 72]
    assert catalog["source"]["revision"] == "22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec"
    assert catalog["capabilities"]["actual_engine_run"] is False


def test_static_geometry_does_not_depend_on_global_decimal_precision() -> None:
    bundle = load_v3_bundle(Path(__file__).parents[2] / "data/v3-proposal")
    expected = build_static_export(bundle)
    with localcontext() as context:
        context.prec = 3
        assert build_static_export(bundle) == expected
