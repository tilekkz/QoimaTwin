"""Independent output-alias regression, authored before the calendar guard correction."""

from pathlib import Path

import pytest

from app.errors import OutputNotEmptyError
from app.v3.cli_coordinator_calendar import materialize_coordinator_calendar_file


def test_calendar_rejects_empty_directory_symlink_before_reading_inputs(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlink creation is unavailable: {exc}")
    # Missing input paths are intentional: rejection must precede reads or compilation.
    with pytest.raises(OutputNotEmptyError):
        materialize_coordinator_calendar_file(
            tmp_path / "missing-source",
            tmp_path / "missing-profile.json",
            tmp_path / "missing-calendar.json",
            alias,
        )
    assert alias.is_symlink()
    assert list(target.iterdir()) == []
