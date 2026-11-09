"""Calendar publication compiles source inputs but never executes the simulation."""

from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.errors import OutputNotEmptyError
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.cli_coordinator_calendar import materialize_coordinator_calendar_file
from app.v3.coordinator_calendar_io import calendar_document
from app.v3.coordinator_calendar_models import CalendarLane, CoordinatorCalendar
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_profile import load_coordinator_inputs
from tests.v3.test_coordinator_profile_fixtures import ROOT, coordinator_document


def inputs(tmp_path: Path) -> tuple[Path, Path]:
    profile, plan = tmp_path / "profile.json", tmp_path / "calendar.json"
    profile.write_bytes(canonical_bytes(coordinator_document()))
    plan.write_bytes(
        canonical_bytes(
            calendar_document(
                CoordinatorCalendar(
                    3_600_000_000,
                    4_500_000_000,
                    "Explicit sparse one-hour illustration",
                    (CalendarLane("picks", "unit_order", ("O1", "O2"), 0, 3_600_000_000),),
                )
            )
        )
    )
    return profile, plan


def test_cli_freezes_exact_choices_and_source_inputs_without_engine_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, plan = inputs(tmp_path)
    out = tmp_path / "result"

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Calendar materialization must not construct or run an engine")

    monkeypatch.setattr(CoordinatorEngine, "__init__", forbidden)
    report = materialize_coordinator_calendar_file(ROOT / "data/v3-proposal", profile, plan, out)
    manifest = parse_json((out / "manifest.json").read_bytes())
    assert report["status"] == "passed"
    assert report["operational_admission"] is False
    assert report["counts"] == {"unit_order": 2, "receipt": 0, "whole_order": 0}
    for row in manifest["files"]:
        raw = (out / row["path"]).read_bytes()
        assert len(raw) == row["bytes"]
        assert sha256(raw).hexdigest() == row["sha256"]
    compiled = load_coordinator_inputs((out / "inputs.json").read_bytes())
    assert compiled.input_hash == report["input_hash"]
    assert parse_json(compiled.frozen_bytes)["choices"] == parse_json(
        (out / "profile.json").read_bytes()
    )


def test_nonempty_output_and_invalid_source_choices_do_not_publish(tmp_path: Path) -> None:
    profile, plan = inputs(tmp_path)
    out = tmp_path / "exists"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_text("keep", encoding="utf-8")
    with pytest.raises(OutputNotEmptyError):
        materialize_coordinator_calendar_file(ROOT / "data/v3-proposal", profile, plan, out)
    assert keep.read_text() == "keep"
    document = coordinator_document()
    document["unit_assignments"][0]["cart_id"] = "missing-cart"
    profile.write_bytes(canonical_bytes(document))
    absent = tmp_path / "absent"
    with pytest.raises(ValueError):
        materialize_coordinator_calendar_file(ROOT / "data/v3-proposal", profile, plan, absent)
    assert not absent.exists()
