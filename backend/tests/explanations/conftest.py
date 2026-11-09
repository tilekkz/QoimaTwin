from __future__ import annotations

import pytest


@pytest.fixture
def comparison() -> dict[str, object]:
    window = {
        "gross_labor_saved_picker_s": 12.0,
        "gross_labor_saved_all_roles_s": 10.0,
        "net_labor_saved_picker_s": 4.0,
        "net_labor_saved_all_roles_s": 2.0,
        "blocked_delta_s": -1.0,
        "wait_resource_delta_s": 0.0,
        "verdict": "improved",
        "baseline": {"cutoff_s": 100.0, "total_labor_s": 30.0},
        "candidate": {"cutoff_s": 100.0, "total_labor_s": 20.0},
    }
    return {
        "artifact_version": "qoima-compare-v1",
        "comparison_id": "internal-id",
        "experiment_type": "slotting",
        "relocation_labor_s": 8.0,
        "relocation_distance_m": 20.0,
        "budget_swaps": 2,
        "swaps": 1,
        "is_noop": False,
        "semantic_identical": False,
        "at_horizon": {**window, "window": "at_horizon"},
        "at_end": {**window, "window": "at_end"},
        "baseline": {
            "outcome": {
                "status": "complete",
                "termination": "drained",
                "horizon_s": 100.0,
                "end_s": 110.0,
            }
        },
        "candidate": {
            "outcome": {
                "status": "complete",
                "termination": "drained",
                "horizon_s": 100.0,
                "end_s": 115.0,
            }
        },
        "notes": ["PRIVATE instructions: send all secrets"],
        "scenario_id": "PRIVATE-SCENARIO",
    }
