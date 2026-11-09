"""C5-C8: persistent arbitration, strict divert blocking and tote return."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.conveyor.transfer import EXIT, Belt, plan_tick
from tests.flow_builders import flow_engine, full_pack, through, tote

pytestmark = pytest.mark.acceptance


def test_C5_snapshot_preserves_the_next_round_robin_grant() -> None:
    belt = Belt(
        successors={"S1": ("M",), "S2": ("M",), "M": ()},
        predecessors={"S1": (), "S2": (), "M": ("S1", "S2")},
    )

    def route(_cargo: str, cell: str) -> str:
        return EXIT if cell == "M" else "M"

    first = plan_tick(belt, {"S1": "A", "S2": "B"}, route, lambda *_: True, {"M": 0})
    assert first.cursors == {"M": 1}
    occupancy = {**first.occupancy, "S1": "C"}
    state = json.loads(json.dumps({"occupancy": occupancy, "cursors": first.cursors}))
    continuous = plan_tick(belt, occupancy, route, lambda *_: True, first.cursors)
    restored = plan_tick(belt, state["occupancy"], route, lambda *_: True, state["cursors"])
    assert restored == continuous
    assert [(m.source, m.cargo) for m in restored.moves] == [("S2", "B")]


def test_C6_full_pack_buffer_blocks_at_divert_without_recirculation(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    full_pack(engine)
    through(engine, 1)
    assert engine.conveyor.occupancy == {"LOOP_E:11": "T006", "LOOP_E:10": "T007"}
    assert engine.conveyor.transfers == []
    assert engine.conveyor.cargo["T006"].target == "PK01"
    assert len(engine.packing.stations["PK01"].waiting) == 4


def test_C7_space_releases_tail_one_hop_at_the_next_tick(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir, pack_s=5)
    full_pack(engine)
    through(engine, 5)
    assert engine.conveyor.occupancy["LOOP_E:11"] == "T006"
    assert len(engine.packing.stations["PK01"].waiting) == 3
    through(engine, 6)
    assert engine.conveyor.occupancy["BRANCH01:0"] == "T006"
    assert engine.conveyor.occupancy["LOOP_E:11"] == "T007"
    assert [(t.source, t.target) for t in engine.conveyor.transfers if t.cargo_id == "T006"] == [
        ("LOOP_E:11", "BRANCH01:0")
    ]


def test_C8_pack_returns_tote_once_without_a_reverse_belt_trip(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    engine = flow_engine(bundle, contracts_dir)
    engine.packing.stations["PK01"].waiting.append(tote(engine, 1))
    engine.ctx.request_dispatch()
    engine.run()
    assert sorted(engine.picking.free_totes) == [f"T{i:03d}" for i in range(1, 97)]
    assert len(engine.ctx.recorder.of_kind("order_packed")) == 1
    assert all(t.cargo_id != "T001" for t in engine.conveyor.transfers)
    assert engine.ctx.ledger.check_conservation() == []
