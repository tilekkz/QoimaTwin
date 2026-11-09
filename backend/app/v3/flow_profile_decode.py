"""Decode only schema-validated exact public choices; source-derived fields are placeholders."""

from fractions import Fraction
from typing import Any

from app.v3.flow_profile_schema import TIME_FIELDS
from app.v3.light_flow_models import (
    FlowActor,
    FlowCart,
    FlowOrder,
    FlowPort,
    FlowProfile,
    FlowStation,
    FlowTimes,
)
from app.v3.runtime_graph import DirectedGraph
from app.v3.stock_models import Container, ContainerRecipe, Placement, StockOwner, StockSeed, Vec3


def rational(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def vector(value: list[dict[str, int]]) -> Vec3:
    return rational(value[0]), rational(value[1]), rational(value[2])


def _recipe(value: dict[str, Any]) -> ContainerRecipe:
    return ContainerRecipe(
        value["recipe_id"],
        value["provenance"],
        value["kind"],
        vector(value["outer"]),
        vector(value["inner"]),
        rational(value["tare_kg"]),
        rational(value["max_gross_kg"]),
        value["max_units"],
        tuple(sorted(value["allowed_archetypes"])),
        rational(value["clearance_m"]),
    )


def _materials(document: dict[str, Any]) -> tuple[Container, ...]:
    recipes = {row["recipe_id"]: _recipe(row) for row in document["recipes"]}
    if len(recipes) != len(document["recipes"]):
        raise ValueError("Duplicate explicit material recipe")
    result = []
    used: set[str] = set()
    for row in document["materials"]:
        if row["recipe_id"] not in recipes:
            raise ValueError("Unknown material recipe")
        used.add(row["recipe_id"])
        result.append(Container(row["container_id"], recipes[row["recipe_id"]], row["owner_id"]))
    if used != set(recipes):
        raise ValueError("Every declared recipe must bind a physical initial container")
    return tuple(sorted(result, key=lambda row: row.container_id))


def _placements(rows: list[dict[str, Any]]) -> tuple[Placement, ...]:
    return tuple(Placement(row["unit_id"], vector(row["position"])) for row in rows)


def _order(row: dict[str, Any]) -> FlowOrder:
    return FlowOrder(
        row["order_id"],
        row["arrival_tick"],
        row["source_hu"],
        "derived",
        row["carrier_id"],
        row["package_id"],
        _placements(row["carrier_placements"]),
        _placements(row["package_placements"]),
    )


def _actors(document: dict[str, Any]) -> tuple[FlowActor, ...]:
    return tuple(
        FlowActor(
            row["actor_id"],
            row["home"],
            rational(row["speed_m_s"]),
            rational(row["max_gross_kg"]),
            row["available_tick"],
        )
        for row in sorted(document["actors"], key=lambda row: row["actor_id"])
    )


def _owners(document: dict[str, Any]) -> tuple[StockOwner, ...]:
    return tuple(
        StockOwner(row["owner_id"], row["kind"], row["capacity"])
        for row in sorted(document["owners"], key=lambda row: row["owner_id"])
    )


def _cart(cart: dict[str, Any]) -> FlowCart:
    return FlowCart(
        cart["cart_id"],
        cart["home"],
        "derived",
        cart["owner_id"],
        rational(cart["speed_m_s"]),
        rational(cart["max_gross_kg"]),
        rational(cart["width_m"]),
    )


def decode_choices(document: dict[str, Any]) -> FlowProfile:
    station, pools = document["station"], document["pool_owners"]
    roles, times = document["roles"], document["times"]
    return FlowProfile(
        document["profile_id"],
        document["provenance"],
        DirectedGraph("unbound", (), ()),
        StockSeed((), (), ()),
        _owners(document),
        _materials(document),
        _actors(document),
        roles["picker_id"],
        roles["packer_id"],
        roles["shipper_id"],
        _cart(document["cart"]),
        FlowStation(
            station["station_id"], "derived", station["bench_owner"], station["empty_owner"]
        ),
        FlowPort(document["port_id"], "derived", 0, ()),
        "derived",
        "derived",
        pools["carrier"],
        pools["package"],
        pools["shipped"],
        (),
        FlowTimes(*(times[key] for key in TIME_FIELDS)),
        tuple(_order(row) for row in sorted(document["orders"], key=lambda row: row["order_id"])),
        path_clearance_m=rational(document["path_clearance_m"]),
    )
