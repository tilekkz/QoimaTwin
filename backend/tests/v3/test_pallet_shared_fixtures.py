"""A declared local fixture, never an extra HU inserted into the pinned530 inventory."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.pallet_cycle_types import PLATFORM_ID
from app.v3.pallet_shared_models import PalletSharedJob, PalletSharedProfile
from app.v3.runtime_graph import DirectedGraph
from app.v3.stock_models import Container, ContainerRecipe, StockOwner, UnitRecipe, UnitToken
from tests.v3.test_pallet_cycle_clock import timing
from tests.v3.test_whole_flow_fixtures import whole_hand_profile

PALLET = "analytical-existing-PALLET"
ANCHOR = "analytical:moving-frame:FL01"
VEHICLE_OWNER = "vehicle:FL01"


def shared_profile(mesh_hash: str, *, jobs: int = 1) -> PalletSharedProfile:
    world = whole_hand_profile("SMALL_CARTON")
    flow = world.receipts.flow
    recipe = UnitRecipe("PALLET_LOAD", (F(".36"), F(".26"), F(".28")), F("17.2"), F(".8"))
    wrapper = ContainerRecipe(
        "C02:PALLET_LOAD",
        "exact pinned C02 local fixture",
        "source_wrapper",
        (F("1.2"), F("1.35"), F(1)),
        None,
        F(23),
        F(455),
        24,
        ("PALLET_LOAD",),
        F(0),
    )
    stock = replace(
        flow.stock,
        units=(
            *flow.stock.units,
            *(
                UnitToken(f"PU{i}", PALLET, "PALLET-SKU", "PALLET-LOT", i, recipe)
                for i in range(1, 25)
            ),
        ),
        containers=(*flow.stock.containers, Container(PALLET, wrapper, PLATFORM_ID)),
        owners=(*flow.stock.owners, StockOwner(PLATFORM_ID, "slot", 1)),
    )
    graph = DirectedGraph(
        "analytical-world-and-moving-frame", (*flow.graph.node_ids, ANCHOR), flow.graph.arcs
    )
    actors = tuple(replace(a, home=ANCHOR) if a.actor_id == "F01" else a for a in flow.actors)
    flow = replace(
        flow,
        stock=stock,
        graph=graph,
        actors=actors,
        owners=(*flow.owners, StockOwner(VEHICLE_OWNER, "vehicle", 1)),
    )
    world = replace(world, receipts=replace(world.receipts, flow=flow), orders=())
    return PalletSharedProfile(
        world,
        timing(),
        tuple(PalletSharedJob(f"C{i}", 0, PALLET, "local_pickup_return") for i in range(jobs)),
        PALLET,
        PLATFORM_ID,
        VEHICLE_OWNER,
        ANCHOR,
        mesh_hash,
        "analytical_hand",
        "seated_in_FL01",
        False,
    )
