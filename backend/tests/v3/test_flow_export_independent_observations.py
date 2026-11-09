"""Hand scalar oracles and exact immutable checkpoint retrieval, without arbitrary replay."""

from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.v3.flow_run import validate_flow_run
from app.v3.flow_transport import captured_checkpoint, event_window, write_flow_run
from tests.v3.test_flow_export_independent_semantics import hand_run
from tests.v3.test_flow_run_fixtures import sample


def fraction(value: dict[str, int]) -> F:
    return F(value["numerator"], value["denominator"])


def units_in(state: dict[str, Any], identity: str) -> set[str]:
    return {r["unit_id"] for r in state["stock"]["locations"] if r["container_id"] == identity}


def file_hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_horizon_and_end_publish_manual_mass_units_and_paid_exposure() -> None:
    run = hand_run()
    horizon, end = run["at_horizon"]["state"], run["at_end"]["state"]
    assert len(units_in(horizon, "HU1")) == 21
    assert units_in(horizon, "P1") == {"U1", "U2", "U3"}
    assert units_in(horizon, "C1") == set()
    owners = {r["container_id"]: r["owner_id"] for r in horizon["stock"]["containers"]}
    assert owners == {"HU1": "slot", "C1": "empties", "P1": "belt:O1"}
    assert fraction(horizon["balance"]["onsite_mass_kg"]) == F(119, 100)
    assert fraction(end["balance"]["onsite_mass_kg"]) == F(207, 200)
    assert fraction(end["balance"]["shipped_mass_kg"]) == F(31, 200)
    assert end["balance"]["units_by_sku"] == [["SKU1", 24]]
    workers = {w["actor_id"]: w for w in horizon["workers"]}
    assert [workers[k]["paid_ticks"] for k in ("P01", "K06", "S01")] == [
        20_000_000,
        6_084_552,
        0,
    ]
    assert horizon["cart"]["node"] == "H" and horizon["cart"]["operation"] is None
    assert run["metrics"]["at_horizon"]["completed_units"] == 0
    assert run["metrics"]["at_end"]["completed_units"] == 3


def test_published_completed_units_cannot_disagree_with_conserved_shipped_units() -> None:
    run = deepcopy(hand_run())
    run["metrics"]["at_end"]["completed_units"] = 999
    with pytest.raises(ValueError):
        validate_flow_run(run)


def test_backward_captured_reads_and_repeat_write_preserve_every_raw_artifact(
    tmp_path: Path,
) -> None:
    compiled, _ = sample()
    write_flow_run(hand_run(), tmp_path, inputs=compiled.frozen_bytes, max_chunk_bytes=32_768)
    initial = file_hashes(tmp_path)
    views = [
        captured_checkpoint(tmp_path, tick) for tick in (0, 60_000_000, 30_000_000, 60_000_000)
    ]
    assert views[1] == views[3]
    assert len(units_in(views[0]["state"], "HU1")) == 24
    assert units_in(views[1]["state"], "P1") == {"U1", "U2", "U3"}
    views[0]["state"]["stock"]["revision"] = 999
    assert captured_checkpoint(tmp_path, 0)["state"]["stock"]["revision"] == 0
    with pytest.raises(ValueError):
        write_flow_run(hand_run(), tmp_path, inputs=compiled.frozen_bytes)
    assert file_hashes(tmp_path) == initial


def test_early_selection_still_validates_later_unselected_file(tmp_path: Path) -> None:
    compiled, _ = sample()
    manifest = write_flow_run(hand_run(), tmp_path, inputs=compiled.frozen_bytes)
    last = manifest["event_chunks"][-1]
    assert last["start_tick"] == 180_000_000
    path = tmp_path / last["path"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        event_window(tmp_path, 0, 1)
    with pytest.raises(ValueError):
        captured_checkpoint(tmp_path, 0)
