"""Code-only calendar peer cases; execution is deferred to the final integration phase."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.errors import OutputNotEmptyError
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import cli_coordinator_calendar as cli
from app.v3.coordinator_calendar import materialize_calendar
from app.v3.coordinator_calendar_io import calendar_document
from app.v3.coordinator_calendar_models import CalendarLane, CoordinatorCalendar
from tests.v3.test_coordinator_profile_fixtures import coordinator_document


def test_output_becoming_nonempty_during_compilation_is_not_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = coordinator_document()
    plan = CoordinatorCalendar(
        10,
        20,
        "Explicit two-job hand clock",
        (CalendarLane("unit", "unit_order", ("O1", "O2"), 0, 10),),
    )
    profile = tmp_path / "profile.json"
    calendar, out = tmp_path / "calendar.json", tmp_path / "out"
    profile.write_bytes(canonical_bytes(document))
    calendar.write_bytes(canonical_bytes(calendar_document(plan)))

    def intercepted_compile(*args: Any, **kwargs: Any) -> Any:
        out.mkdir()
        (out / "keep.txt").write_bytes(b"unrelated existing bytes")
        return SimpleNamespace(
            frozen_bytes=canonical_bytes({"choices": args[2]}),
            input_hash="mock-compiler-hash",
        )

    monkeypatch.setattr(cli, "load_v3_bundle", lambda _: SimpleNamespace(source_revision="mock"))
    monkeypatch.setattr(cli, "load_conveyor_source", lambda _: None)
    monkeypatch.setattr(cli, "compile_coordinator_profile", intercepted_compile)
    with pytest.raises(OutputNotEmptyError):
        cli.materialize_coordinator_calendar_file(tmp_path / "unused", profile, calendar, out)
    assert {path.name for path in out.iterdir()} == {"keep.txt"}
    assert (out / "keep.txt").read_bytes() == b"unrelated existing bytes"


def test_integer_calendar_above_float_precision_preserves_exact_half_open_ticks() -> None:
    start = 9_007_199_254_740_993
    plan = CoordinatorCalendar(
        start + 5,
        start + 10,
        "Exact arithmetic only; not a physical run duration",
        (CalendarLane("unit", "unit_order", ("O1", "O2"), start, start + 5),),
    )
    result = materialize_calendar(coordinator_document(), plan)
    choices = parse_json(result.choices_bytes)
    assert [row["arrival_tick"] for row in choices["orders"]] == [
        9_007_199_254_740_993,
        9_007_199_254_740_995,
    ]
    assert all(row["arrival_tick"] < start + 5 for row in choices["orders"])
    assert result.operational_admission is False
