"""Conveyor cell topology compiled from layout ports (ADR 0004)."""

from __future__ import annotations

import pytest

from app.contracts.layout import Layout
from app.conveyor.topology import ConveyorTopology, ExitKind


@pytest.fixture(scope="module")
def topo(layout: Layout) -> ConveyorTopology:
    return ConveyorTopology.from_layout(layout)


def test_total_cell_count_is_179(topo: ConveyorTopology) -> None:
    assert len(topo.cells) == 179
    assert sum(1 for c in topo.cells if c.startswith(("LOOP_E:", "LOOP_W:", "LOOP_TURN_"))) == 112


def test_feed_enters_loop_west_at_documented_offsets(topo: ConveyorTopology) -> None:
    assert topo.successors["FEED01:0"] == ("LOOP_W:52",)
    assert topo.successors["FEED02:0"] == ("LOOP_W:34",)
    assert topo.successors["FEED03:0"] == ("LOOP_W:16",)


def test_branches_leave_loop_east_after_documented_cells(topo: ConveyorTopology) -> None:
    for pack_index, index in enumerate((11, 17, 23, 29, 35, 41), 1):
        assert topo.successors[f"LOOP_E:{index}"] == (
            f"BRANCH{pack_index:02d}:0",
            f"LOOP_E:{index + 1}",
        )


def test_outfeeds_join_out_main(topo: ConveyorTopology) -> None:
    for pack_index, offset in enumerate((0, 6, 12, 18, 24, 30), 1):
        assert topo.successors[f"OUTFEED{pack_index:02d}:0"] == (f"OUT_MAIN:{offset}",)


def test_merge_cells_have_two_ordered_predecessors(topo: ConveyorTopology) -> None:
    assert topo.predecessors["LOOP_W:52"] == ("FEED01:0", "LOOP_W:51")
    assert topo.predecessors["LOOP_E:0"] == ("LOOP_TURN_W:1",)
    assert topo.predecessors["OUT_MAIN:6"] == ("OUTFEED02:0", "OUT_MAIN:5")


def test_exits_lead_to_pack_buffers_and_shipping(topo: ConveyorTopology) -> None:
    for i in range(1, 7):
        exit_ = topo.exits[f"BRANCH{i:02d}:1"]
        assert exit_.kind is ExitKind.PACK_BUFFER
        assert exit_.target_id == f"PK{i:02d}"
    shipping = topo.exits["OUT_MAIN:45"]
    assert shipping.kind is ExitKind.SHIPPING_BUFFER
    assert len(topo.exits) == 7


def test_inlets_are_feeds_and_outfeeds(topo: ConveyorTopology) -> None:
    assert topo.induction_inlets == {"I01": "FEED01:0", "I02": "FEED02:0", "I03": "FEED03:0"}
    assert topo.pack_outlets == {f"PK{i:02d}": f"OUTFEED{i:02d}:0" for i in range(1, 7)}


def test_I01_to_PK01_takes_19_cells(topo: ConveyorTopology) -> None:
    assert topo.travel_cells("FEED01:0", "BRANCH01:1") == 19


def test_PK01_to_shipping_takes_47_cells(topo: ConveyorTopology) -> None:
    assert topo.travel_cells("OUTFEED01:0", "OUT_MAIN:45") == 47


def test_every_induction_reaches_every_pack_station(topo: ConveyorTopology) -> None:
    for induction, inlet in topo.induction_inlets.items():
        for pack in topo.pack_outlets:
            assert topo.travel_cells(inlet, f"BRANCH{pack[2:]}:1") >= 1, (induction, pack)


def test_route_next_hop_follows_target_branch(topo: ConveyorTopology) -> None:
    assert topo.next_cell_towards("LOOP_E:11", "PK01") == "BRANCH01:0"
    assert topo.next_cell_towards("LOOP_E:11", "PK02") == "LOOP_E:12"
    assert topo.next_cell_towards("BRANCH01:1", "PK01") is None
