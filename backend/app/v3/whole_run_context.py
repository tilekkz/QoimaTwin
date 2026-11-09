"""Typed physical context reconstructed only from the publication's immutable catalog."""

from app.v3.interface import Json
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_run_profile import decode_profile


def profile_from_catalog(catalog: Json) -> WholeFlowProfile:
    flow = catalog["workflow_profile"]
    recipes = {r["recipe_id"]: r for r in catalog["container_recipes"]}
    containers = [
        {
            "container_id": c["container_id"],
            "recipe": recipes[c["recipe_id"]],
            "owner_id": c["initial_owner_id"],
            "sealed_for": c["initial_sealed_for"],
        }
        for c in catalog["initial_containers"]
    ]
    extra_owners = {o["owner_id"] for o in flow["owners"]}
    physical = {
        "profile": flow,
        "graph": catalog["graph"],
        "initial_state": {
            "stock": {"containers": containers},
            "source_units": catalog["initial_units"],
            "source_owners": [o for o in catalog["owners"] if o["owner_id"] not in extra_owners],
        },
        "receipt_process": catalog["receipt_process"],
        "whole_process": catalog["whole_process"],
    }
    return decode_profile(physical)
