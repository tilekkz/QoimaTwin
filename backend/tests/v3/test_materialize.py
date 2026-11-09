"""Boundary failures of fixed explicit clocks, independent of an engine."""

import json
from pathlib import Path

import pytest

from app.v3.materialize import materialize_jobs
from app.v3.profile_models import ManualProposal

DEMO = Path(__file__).parents[2] / "data/v3-execution-proposals/manual-whole-hu-demo-v1.json"


@pytest.mark.parametrize(
    "field,value",
    [
        ("horizon_tick", True),
        ("horizon_tick", 1.5),
        ("horizon_tick", 0),
        ("end_tick", -1),
        ("calendar_policy", "forecast-from-unclocked-moves"),
    ],
)
def test_calendar_rejects_invalid_policy_and_clocks(field: str, value: object) -> None:
    raw = json.loads(DEMO.read_bytes())
    raw[field] = value
    with pytest.raises(ValueError):
        materialize_jobs(ManualProposal.model_validate(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("arrival_seconds", "nan"),
        ("arrival_seconds", "-0.1"),
        ("arrival_seconds", "600"),
        ("arrival_seconds", True),
        ("job_id", ""),
        ("job_id", "   "),
    ],
)
def test_job_rejects_bad_arrival_and_identity(field: str, value: object) -> None:
    raw = json.loads(DEMO.read_bytes())
    raw["jobs"][0][field] = value
    with pytest.raises(ValueError):
        materialize_jobs(ManualProposal.model_validate(raw))


def test_duplicate_whole_hu_job_rejects() -> None:
    raw = json.loads(DEMO.read_bytes())
    raw["jobs"][1]["hu_id"] = raw["jobs"][0]["hu_id"]
    with pytest.raises(ValueError, match="unique HU"):
        materialize_jobs(ManualProposal.model_validate(raw))
