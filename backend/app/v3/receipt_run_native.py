"""Validate immutable native values before replacing them with compact catalog references."""

from app.v3.flow_profile_wire import record
from app.v3.interface import Json
from app.v3.receipt_flow_models import ReceiptFlowOutcome
from app.v3.receipt_run_journal import same
from app.v3.stock_models import Container


def validate_native(catalog: Json, outcome: ReceiptFlowOutcome) -> None:
    recipes = {r["recipe_id"]: r for r in catalog["container_recipes"]}
    containers = {c["container_id"]: recipes[c["recipe_id"]] for c in catalog["initial_containers"]}
    units = {u["unit_id"]: u for u in catalog["initial_units"]}
    definitions = {}
    for offer in catalog["declared_receipts"]:
        definition = offer["definition"]
        definitions[definition["receipt_id"]] = definition
        containers[definition["hu_id"]] = recipes[offer["container_recipe_id"]]
        units.update((u["unit_id"], u) for u in offer["units"])
    for snapshot in (*outcome.checkpoints, outcome.at_horizon, outcome.at_end):
        for container in (*snapshot.stock.containers, *snapshot.inventory.containers):
            _container(container, containers)
        for definition in snapshot.inventory.registered_receipts:
            same(
                record(definition),
                definitions.get(definition.receipt_id),
                "Native registered definition differs from declared receipt",
            )
    for event in outcome.events:
        if event.delta is None:
            continue
        for contents in (*event.delta.before, *event.delta.after):
            _container(contents.container, containers)
            for unit in contents.units:
                same(
                    record(unit.token),
                    units.get(unit.token.unit_id),
                    "Native unit ancestry differs from immutable source/receipt declaration",
                )


def _container(container: Container, recipes: dict[str, Json]) -> None:
    same(
        record(container.recipe),
        recipes.get(container.container_id),
        "Native container recipe differs from immutable physical catalog",
    )
