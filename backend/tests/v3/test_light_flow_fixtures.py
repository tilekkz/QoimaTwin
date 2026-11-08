"""Explicit synthetic process choices; human distances are the independent hand oracle."""

from fractions import Fraction as F

from app.v3.execution_types import ACTOR_IDS
from app.v3.light_flow_models import (
    FlowActor,
    FlowCart,
    FlowOrder,
    FlowPort,
    FlowProfile,
    FlowStation,
    FlowTimes,
)
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import Container, ContainerRecipe, Placement, StockOwner
from tests.v3.test_belt_runtime import full_route
from tests.v3.test_stock_fixtures import source_seed_fixture

SECOND = 1_000_000


def hand_graph() -> DirectedGraph:
    edges = ("H SLOT 2", "SLOT PARK 3", "PARK IN 1", "KH PACK 2", "SH OUT 2", "OUT PORT 3")
    arcs = []
    for index, edge in enumerate(edges):
        a, b, distance = edge.split()
        modes = frozenset({"pedestrian", "manual_cart"} if index < 2 else {"pedestrian"})
        for source, target in ((a, b), (b, a)):
            arcs.append(
                Arc(
                    f"{source}-{target}",
                    source,
                    target,
                    F(distance),
                    F(distance),
                    modes=modes,
                    cargo_classes=frozenset({"SMALL_CARTON"}),
                    clear_width_m=F(2),
                    clear_height_m=F(3),
                )
            )
    nodes = {value for arc in arcs for value in (arc.source, arc.target)}
    return DirectedGraph("hand-light", sorted(nodes), arcs)


def material_recipe(kind: str) -> ContainerRecipe:
    carrier = kind == "carrier"
    outer = (F(".6"), F(".34"), F(".4")) if carrier else (F(".24"), F(".12"), F(".12"))
    inner = (F(".56"), F(".30"), F(".36")) if carrier else (F(".22"), F(".10"), F(".10"))
    return ContainerRecipe(
        f"hand-{kind}-v1",
        "ADR0045 explicit test material",
        kind,
        outer,
        inner,
        F(".20") if carrier else F(".05"),
        F(10),
        6,
        ("SMALL_CARTON",),
        F(0),
    )


def hand_orders(count: int) -> tuple[FlowOrder, ...]:
    result = []
    for index in range(count):
        units = tuple(
            Placement(f"U{3 * index + n + 1}", (F(7 * n, 100), F(0), F(0))) for n in range(3)
        )
        result.append(
            FlowOrder(
                f"O{index + 1}", 0, "HU1", "SLOT", f"C{index + 1}", f"P{index + 1}", units, units
            )
        )
    return tuple(result)


def hand_owners(orders: int) -> tuple[StockOwner, ...]:
    return tuple(
        StockOwner(name, kind, capacity)
        for name, kind, capacity in (
            ("carrier-pool", "material", orders),
            ("package-pool", "material", orders),
            ("cart", "workstation", 1),
            ("actor:P01", "workstation", 1),
            ("actor:S01", "workstation", 1),
            ("bench", "workstation", 1),
            ("empties", "workstation", orders),
            ("shipped", "shipped", orders),
            *((f"belt:O{i + 1}", "workstation", 1) for i in range(orders)),
        )
    )


def hand_profile(*, orders: int = 1, packer_ready: int = 0, shipper_ready: int = 0) -> FlowProfile:
    actors = tuple(
        FlowActor(
            identity,
            "KH" if identity == "K06" else "SH" if identity == "S01" else "H",
            F(1),
            F(10),
            packer_ready if identity == "K06" else shipper_ready if identity == "S01" else 0,
        )
        for identity in ACTOR_IDS
    )
    materials = tuple(
        Container(f"{prefix}{i + 1}", material_recipe(kind), owner)
        for i in range(orders)
        for prefix, kind, owner in (
            ("C", "carrier", "carrier-pool"),
            ("P", "package", "package-pool"),
        )
    )
    return FlowProfile(
        "hand-light-v1",
        "explicit hand human graph and services",
        hand_graph(),
        source_seed_fixture(),
        hand_owners(orders),
        materials,
        actors,
        "P01",
        "K06",
        "S01",
        FlowCart("CART01", "H", "PARK", "cart", F(1), F(10), F(".72")),
        FlowStation("PK06", "PACK", "bench", "empties"),
        FlowPort("OUT_S_EXPRESS", "PORT", 20 * SECOND, ((0, 28800 * SECOND),)),
        "IN",
        "OUT",
        "carrier-pool",
        "package-pool",
        "shipped",
        full_route(),
        FlowTimes(SECOND, SECOND, SECOND, SECOND, SECOND, 3 * SECOND, SECOND, SECOND),
        hand_orders(orders),
        path_clearance_m=F(".02"),
    )
