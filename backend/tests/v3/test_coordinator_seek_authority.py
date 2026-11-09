"""Seek remains strict publication authority; it does not invoke a scheduler or trust a cap."""

from copy import deepcopy
from fractions import Fraction
from typing import Any, cast

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_seek import replay_coordinator
from tests.v3.test_coordinator_seek_fixtures import fresh_run
from tests.v3.test_receipt_flow_fixtures import SECOND


@pytest.mark.parametrize("tick", [True, -1, 200_000_001, Fraction(102_000_000), 102.0])
def test_seek_rejects_non_integer_or_unobserved_boundaries(tick: object) -> None:
    inputs, run, _ = fresh_run("roles")
    with pytest.raises(ValueError):
        replay_coordinator(run, inputs=inputs.frozen_bytes, tick=cast(int, tick))


def test_seek_preserves_raw_values_and_never_invokes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs, run, _ = fresh_run("roles")
    original = canonical_bytes(run)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("A data-only seek cannot execute the runtime")

    monkeypatch.setattr(CoordinatorEngine, "run", forbidden)
    initial = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=0)
    middle = replay_coordinator(run, inputs=inputs.frozen_bytes, tick=102 * SECOND)
    assert initial.last_seq == -1
    assert middle.last_seq == max(
        e["seq"] for e in run["outcome"]["events"] if e["tick"] <= 102 * SECOND
    )
    assert canonical_bytes(run) == original


def test_seek_rejects_rehashed_missing_cart_and_retained_input_mismatch() -> None:
    inputs, run, _ = fresh_run("roles")
    wrong = deepcopy(run)
    wrong["outcome"]["at_end"]["carts"] = []
    with pytest.raises(ValueError):
        replay_coordinator(wrong, inputs=inputs.frozen_bytes, tick=102 * SECOND)
    wrong = deepcopy(run)
    wrong["input_hash"] = "a" * 64
    with pytest.raises(ValueError):
        replay_coordinator(wrong, inputs=inputs.frozen_bytes, tick=102 * SECOND)
