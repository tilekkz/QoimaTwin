"""Rehashing a captured state must not legitimize broken physical balances or mutations."""

from copy import deepcopy
from functools import cache
from typing import Any

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.flow_run import build_flow_run, validate_flow_run
from tests.v3.test_flow_run_fixtures import sample


@cache
def hand_run() -> dict[str, Any]:
    return build_flow_run(*sample())


@pytest.mark.parametrize("corruption", ["mass", "sku_count", "owner_capacity", "delta_units"])
def test_self_consistently_rehashed_physical_corruption_is_rejected(corruption: str) -> None:
    run = deepcopy(hand_run())
    point = next(c for c in run["checkpoints"] if c["tick"] == 30_000_000)
    state = point["state"]
    if corruption == "mass":
        state["balance"]["onsite_mass_kg"] = {"numerator": 0, "denominator": 1}
    elif corruption == "sku_count":
        state["balance"]["units_by_sku"] = [["SKU1", 999]]
    elif corruption == "owner_capacity":
        for container in state["stock"]["containers"]:
            if container["container_id"] in {"HU1", "P1"}:
                container["owner_id"] = "cart"  # Two known containers in one declared position.
    else:
        delta = next(
            e["delta"]
            for e in run["events"]
            if e["delta"] is not None and e["delta"]["operation"] == "pick"
        )
        delta["unit_ids"] = [delta["unit_ids"][0]] * 3
    point["state_hash"] = sha256_hex(state)
    with pytest.raises(ValueError):
        validate_flow_run(run)
