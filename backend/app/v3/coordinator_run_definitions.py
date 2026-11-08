"""Immutable source and declared receipt definitions never bootstrap current inventory."""

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_native_decode import encode
from app.v3.interface import Json
from app.v3.stock_receipts import receipt_recipes, receipt_tokens


class Definitions:
    def __init__(self, profile: CoordinatorProfile) -> None:
        flow = profile.world.receipts.flow
        self.containers: dict[str, Json] = {
            c.container_id: encode(c.recipe) for c in (*flow.stock.containers, *flow.materials)
        }
        self.units: dict[str, Json] = {u.unit_id: encode(u) for u in flow.stock.units}
        self.receipts: dict[str, Json] = {}
        source_tokens = {u.unit_id: u for u in flow.stock.units}
        source_containers = {c.container_id: c for c in flow.stock.containers}
        for offer in profile.world.receipts.receipts:
            definition = offer.definition
            recipe, wrapper = receipt_recipes(definition.sku_id, source_tokens, source_containers)
            if definition.hu_id in self.containers or definition.receipt_id in self.receipts:
                raise ValueError("Duplicate declared receipt identity")
            self.receipts[definition.receipt_id] = encode(definition)
            self.containers[definition.hu_id] = encode(wrapper)
            for token in receipt_tokens(definition, recipe):
                if token.unit_id in self.units:
                    raise ValueError("Declared receipt unit ancestry conflicts with baseline")
                self.units[token.unit_id] = encode(token)

    def container(self, value: Json) -> Json:
        if value.keys() != {"container_id", "owner_id", "sealed_for"}:
            raise ValueError("Compact container has missing or unknown fields")
        if type(value["container_id"]) is not str:
            raise ValueError("Compact container requires an exact identity")
        recipe = self.containers.get(value["container_id"])
        if recipe is None:
            raise ValueError("Unknown compact container reference")
        return {**value, "recipe": recipe}

    def unit(self, value: Json) -> Json:
        if (
            value.keys() != {"unit_id"}
            or type(value["unit_id"]) is not str
            or value["unit_id"] not in self.units
        ):
            raise ValueError("Unknown compact unit reference or fields")
        return self.units[value["unit_id"]]

    def receipt(self, value: Json) -> Json:
        if (
            value.keys() != {"receipt_id"}
            or type(value["receipt_id"]) is not str
            or value["receipt_id"] not in self.receipts
        ):
            raise ValueError("Unknown compact receipt reference or fields")
        return self.receipts[value["receipt_id"]]
