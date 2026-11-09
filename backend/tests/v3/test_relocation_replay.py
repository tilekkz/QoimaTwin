"""Independent arbitrary-cut N1 reader expectations, with all scheduler entry points blocked."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import cache
from typing import cast
from unittest.mock import patch

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.api_coordinator_replay_projection import project_snapshot as project_base
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import load_run_inputs as load_common
from app.v3.coordinator_seek import replay_coordinator
from app.v3.interface import Json
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_replay import replay_relocation_run
from app.v3.relocation_run import build_relocation_run
from app.v3.relocation_run_inputs import HandRelocationInputs, freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


@cache
def replay_case(noop: bool = False) -> tuple[HandRelocationInputs, Json, CoordinatorOutcome]:
    profile = relocation_hand(whole_arrival=SECOND if noop else None)
    if noop:
        profile = replace(profile, jobs=())
    horizon, cap = (20 * SECOND, 100 * SECOND) if noop else (10 * SECOND, 20 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), horizon, cap)
    outcome = RelocationEngine(profile, receipt_conveyor()).run(horizon, cap)
    return inputs, build_relocation_run(inputs, outcome), outcome


def read(run: Json, inputs: bytes, tick: int) -> Json:
    with (
        patch.object(RelocationEngine, "run", side_effect=AssertionError("Reader ran N1 engine")),
        patch.object(LightFlowEngine, "run", side_effect=AssertionError("Reader ran base engine")),
        patch.object(
            CoordinatorEngine, "__init__", side_effect=AssertionError("Reader restored engine")
        ),
    ):
        return replay_relocation_run(run, inputs=inputs, tick=tick)


@pytest.mark.parametrize(
    ("tick", "owner", "revision", "stage"),
    [
        (0, "slot", 0, "relocation_approach"),
        (3 * SECOND, "slot", 0, "relocation_take"),
        (4 * SECOND, "actor:S01", 1, "relocation_carry"),
        (6 * SECOND, "actor:S01", 1, "relocation_carry"),
        (8 * SECOND, "target", 2, "relocation_return"),
        (9 * SECOND, "target", 2, "relocation_return"),
        (13 * SECOND - 1, "target", 2, "relocation_return"),
        (13 * SECOND, "target", 2, None),
    ],
)
def test_arbitrary_hand_cut_preserves_custody_claims_and_actual_paid_time(
    tick: int,
    owner: str,
    revision: int,
    stage: str | None,
) -> None:
    inputs, run, outcome = replay_case()
    frame = read(run, inputs.frozen_bytes, tick)
    state = frame["snapshot"]
    container = next(c for c in state["stock"]["containers"] if c["container_id"] == "HU1")
    assert container["owner_id"] == owner
    assert state["stock"]["revision"] == revision
    worker = next(w for w in state["workers"] if w["actor_id"] == "S01")
    assert worker["paid_ticks"] == tick and worker["queue_ticks"] == 0
    assert (worker["operation"]["kind"] if worker["operation"] else None) == stage
    held = tick < 13 * SECOND
    assert len(state["inventory"]["claims"]) == int(held)
    assert len(state["leases"]) == 3 * int(held)
    assert state["inventory"]["claim_generation"] == (1 if held else 2)
    assert state["stock"]["locations"] == run["outcome"]["checkpoints"][0]["stock"]["locations"]
    assert state["balance"] == run["outcome"]["checkpoints"][0]["balance"]
    if held:
        claim = state["inventory"]["claims"][0]
        assert len(claim["unit_ids"]) == len(set(claim["unit_ids"])) == 24
        assert claim["container_id"] == "HU1" and claim["job_id"] == "N1"
    if stage in {"relocation_approach", "relocation_carry", "relocation_return"}:
        assert worker["node"] is None
    assert state["derived_sources"] == ([] if tick < 8 * SECOND else [["HU1", "target"]])
    assert frame["last_seq"] == sum(e.tick <= tick for e in outcome.events) - 1
    assert frame["run_id"] == run["run_id"] and frame["input_hash"] == inputs.input_hash
    assert frame["reader_capabilities"] == {
        "arbitrary_settled_state": True,
        "engine_restore": False,
        "geometric_interpolation": False,
        "full_v3": False,
    }


def test_repeated_backward_reads_are_pure_and_equal_saved_captures() -> None:
    inputs, run, outcome = replay_case()
    before = canonical_bytes(run)
    late = read(run, inputs.frozen_bytes, 13 * SECOND)
    early = read(run, inputs.frozen_bytes, 6 * SECOND)
    read(run, inputs.frozen_bytes, 3 * SECOND)
    assert canonical_bytes(read(run, inputs.frozen_bytes, 13 * SECOND)) == canonical_bytes(late)
    assert canonical_bytes(read(run, inputs.frozen_bytes, 6 * SECOND)) == canonical_bytes(early)
    for name, point in (("at_horizon", outcome.at_horizon), ("at_end", outcome.at_end)):
        assert read(run, inputs.frozen_bytes, point.tick)["snapshot"] == run["outcome"][name]
    assert read(run, inputs.frozen_bytes, 0)["snapshot"] == run["outcome"]["checkpoints"][0]
    assert canonical_bytes(run) == before


@pytest.mark.parametrize("tick", [True, Fraction(1), -1, 13 * SECOND + 1, 20 * SECOND])
def test_invalid_or_unobserved_cut_cannot_be_inferred(tick: object) -> None:
    inputs, run, _ = replay_case()
    with pytest.raises(ValueError):
        replay_relocation_run(run, inputs=inputs.frozen_bytes, tick=cast(int, tick))


def test_full_future_evidence_is_verified_before_an_earlier_read() -> None:
    inputs, run, _ = replay_case()
    corrupted = deepcopy(run)
    corrupted["outcome"]["at_end"]["relocations"][0]["returned_tick"] = 12 * SECOND
    with pytest.raises(ValueError):
        read(corrupted, inputs.frozen_bytes, 0)


def test_empty_extension_snapshot_equals_original_coordinator_reader() -> None:
    inputs, run, outcome = replay_case(True)
    common = load_common(inputs.common_inputs)
    original = build_coordinator_run(common, outcome)
    expected = replay_coordinator(original, inputs=inputs.common_inputs, tick=3 * SECOND)
    frame = read(run, inputs.frozen_bytes, 3 * SECOND)
    assert frame["outcome_kind"] == "base_noop"
    assert frame["snapshot"] == project_base(common.profile, expected)
    assert "relocations" not in frame["snapshot"]
