"""New source commands remain explicit and preserve the existing V3 dispatch vocabulary."""

from pathlib import Path
from typing import Any

import pytest

from app.v3 import cli


def test_new_coordinator_parser_requires_explicit_profile_and_calendar(tmp_path: Path) -> None:
    args = cli.build_parser().parse_args(
        [
            "materialize-coordinator-calendar",
            "--profile",
            "p.json",
            "--calendar",
            "c.json",
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert args.profile == Path("p.json")
    assert args.calendar == Path("c.json")
    assert args.command == "materialize-coordinator-calendar"
    simulated = cli.build_parser().parse_args(
        [
            "simulate-coordinator",
            "--profile",
            "p.json",
            "--out",
            str(tmp_path / "run"),
        ]
    )
    assert simulated.profile == Path("p.json")


def test_coordinator_dispatch_uses_its_own_source_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[Any, ...]] = []

    def fake(*args: Any) -> dict[str, Any]:
        seen.append(args)
        return {"status": "partial", "test_double": "dispatch only"}

    monkeypatch.setattr(cli, "simulate_coordinator_file", fake)
    args = cli.build_parser().parse_args(
        [
            "simulate-coordinator",
            "--inputs",
            "source",
            "--profile",
            "p.json",
            "--out",
            str(tmp_path / "run"),
        ]
    )
    assert cli._execute(args)["status"] == "partial"
    assert seen == [(Path("source"), Path("p.json"), tmp_path / "run")]


def test_pair_parser_requires_two_explicit_profiles_and_supported_scenario(tmp_path: Path) -> None:
    args = cli.build_parser().parse_args(
        [
            "compare-coordinator",
            "--baseline",
            "before.json",
            "--candidate",
            "after.json",
            "--scenario",
            "N4",
            "--out",
            str(tmp_path / "pair"),
        ]
    )
    assert args.baseline == Path("before.json")
    assert args.candidate == Path("after.json")
    assert args.scenario == "N4"
