"""Count real validation boundaries, independently of wall-clock noise and import aliases."""

import sys
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import FrameType

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3 import api_coordinator_fullness, api_coordinator_readers, api_coordinator_replay
from app.v3.coordinator_run import validate_coordinator_run
from app.v3.coordinator_seek import replay_coordinator
from app.v3.coordinator_transport import read_coordinator_run
from app.v3.storage_fullness_publication import build_fullness_report
from tests.v3.test_native_read_context_fixtures import NativeCase, forbid_engine, native_case

__all__ = ["native_case"]


@contextmanager
def measured_calls() -> Iterator[Counter[str]]:
    counts: Counter[str] = Counter()
    targets = {
        ("app.v3.coordinator_run_inputs", "load_run_inputs"),
        ("app.v3.coordinator_run_validation", "validate_outcome"),
    }

    def observe(frame: FrameType, event: str, _arg: object) -> None:
        key = (frame.f_globals.get("__name__"), frame.f_code.co_name)
        if event == "call" and key in targets:
            counts[frame.f_code.co_name] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        yield counts
    finally:
        sys.setprofile(previous)


@pytest.mark.parametrize("operation", ["read", "validate", "fullness", "replay"])
def test_direct_public_read_performs_one_fresh_native_validation(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    case = native_case
    forbid_engine(monkeypatch)
    calls: dict[str, Callable[[], object]] = {
        "read": lambda: read_coordinator_run(case.root / "run"),
        "validate": lambda: validate_coordinator_run(case.run, inputs=case.inputs.frozen_bytes),
        "fullness": lambda: build_fullness_report(case.run, inputs=case.inputs.frozen_bytes),
        "replay": lambda: replay_coordinator(case.run, inputs=case.inputs.frozen_bytes, tick=0),
    }
    before = canonical_bytes(case.run)
    with measured_calls() as counts:
        calls[operation]()
    assert canonical_bytes(case.run) == before
    assert dict(counts) == {"load_run_inputs": 1, "validate_outcome": 1}


@pytest.mark.parametrize("operation", ["replay", "fullness"])
def test_cold_and_warm_api_projection_each_validate_once(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    case = native_case
    forbid_engine(monkeypatch)
    api_coordinator_readers._validated.cache_clear()
    calls: dict[str, Callable[[], object]] = {
        "replay": lambda: api_coordinator_replay.replay(
            case.store, case.identifier, 0, case.frozen
        ),
        "fullness": lambda: api_coordinator_fullness.storage_fullness(
            case.store, case.identifier, case.frozen
        ),
    }
    counts_and_results = []
    for _ in range(2):
        with measured_calls() as counts:
            result = calls[operation]()
        counts_and_results.append((dict(counts), canonical_bytes(result)))
    assert counts_and_results[0][1] == counts_and_results[1][1]
    assert [row[0] for row in counts_and_results] == [
        {"load_run_inputs": 1, "validate_outcome": 1},
        {"load_run_inputs": 1, "validate_outcome": 1},
    ]
