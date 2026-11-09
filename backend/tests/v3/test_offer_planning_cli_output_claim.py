"""Two real request writers cannot publish failure evidence into the winning output."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from typing import Any

import pytest

from app.errors import OutputNotEmptyError, require_empty_output
from app.v3 import offer_planning_cli_pipeline as pipeline
from app.v3 import offer_planning_cli_storage as storage
from app.v3.offer_planning_cli_models import PlanningFiles


def raw_files(root: Path) -> PlanningFiles:
    root.mkdir()
    paths = tuple(
        root / name for name in ("history.csv", "history.json", "projection.json", "place.json")
    )
    for path, raw in zip(paths, (b"unparsed-test-history\n", b"{}", b"{}", b"{}"), strict=True):
        path.write_bytes(raw)
    return PlanningFiles(*paths)


def publish_stub(root: Path) -> dict[str, Any]:
    for name in (
        "history",
        "forecast",
        "projection",
        "stock",
        "decision",
        "observations",
        "manifest",
    ):
        storage.put(root, name + ".json", b'{"test":"storage-only"}')
    return {"status": "no-op", "test": "storage-only"}


@pytest.mark.parametrize("precreated", [False, True])
def test_concurrent_request_loser_cannot_poison_winning_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, precreated: bool
) -> None:
    paths, output = raw_files(tmp_path / "caller"), tmp_path / "output"
    if precreated:
        output.mkdir()
    checked, loser_finished = Barrier(2, timeout=30), Event()
    genuine_check = require_empty_output
    calculations: list[str] = []

    def after_genuine_empty_check(path: Path) -> None:
        genuine_check(path)
        checked.wait()

    def calculate(root: Path, model: str, raw: dict[str, bytes], request: bytes) -> dict[str, Any]:
        calculations.append(model)
        assert (root / "request.json").read_bytes() == request
        assert (root / "raw/history.csv").read_bytes() == raw["history.csv"]
        assert loser_finished.wait(30), "The competing request did not finish"
        return publish_stub(root)

    def invoke() -> dict[str, Any] | Exception:
        try:
            return pipeline.plan_offer_files(paths, "mean28", output)
        except Exception as exc:
            loser_finished.set()
            return exc

    monkeypatch.setattr(storage, "require_empty_output", after_genuine_empty_check)
    monkeypatch.setattr(pipeline, "_calculate", calculate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: invoke(), range(2)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, FileExistsError) for result in results) == 1
    assert calculations == ["mean28"] and (output / "manifest.json").is_file()
    assert not (output / "failure.json").exists(), "The losing writer poisoned the winning bundle"
    storage.closed_inventory(output)
    assert len([path for path in output.rglob("*") if path.is_file()]) == 12


def test_claimed_raw_read_failure_is_retained_and_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, output = raw_files(tmp_path / "caller"), tmp_path / "output"
    paths.history.unlink()

    def forbidden(*args: object, **kwargs: object) -> dict[str, Any]:
        pytest.fail("Invalid raw input reached a planning calculation")

    monkeypatch.setattr(pipeline, "_calculate", forbidden)
    with pytest.raises(ValueError, match="Bounded regular"):
        pipeline.plan_offer_files(paths, "mean28", output)
    assert (output / "raw").is_dir() and not list((output / "raw").iterdir())
    assert not (output / "manifest.json").exists()
    failure = (output / "failure.json").read_bytes()
    paths.history.write_bytes(b"repaired-raw-test-input\n")
    with pytest.raises(OutputNotEmptyError):
        pipeline.plan_offer_files(paths, "mean28", output)
    assert (output / "failure.json").read_bytes() == failure
    assert {path.name for path in output.iterdir()} == {"raw", "failure.json"}
