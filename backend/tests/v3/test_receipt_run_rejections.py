"""Independent corruptions cannot turn offered stock or missing claims into actual authority."""

from copy import deepcopy
from typing import Any

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.receipt_run import build_receipt_run, validate_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def _rehash(run: dict[str, Any]) -> None:
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        point["state_hash"] = sha256_hex(point["state"])


@pytest.mark.parametrize(
    "forgery", ["mass", "units", "created", "future", "claims", "resource", "return"]
)
def test_rehashed_receipt_forgery_is_rejected(forgery: str) -> None:
    run = deepcopy(build_receipt_run(*sample(), validate=False))
    _corrupt(run, forgery)
    _rehash(run)
    with pytest.raises(ValueError):
        validate_receipt_run(run)


def _corrupt(run: dict[str, Any], kind: str) -> None:
    if kind == "mass":
        run["checkpoints"][1]["state"]["balance"]["onsite_mass_kg"]["numerator"] = 0
    elif kind == "units":
        run["receipt_metrics"]["at_end"]["credited_units"] = 48
    elif kind == "created":
        delta = next(e["delta"] for e in run["events"] if e["kind"] == "receipt_credited")
        delta["created_tokens"][0]["ordinal"] = True
    elif kind == "future":
        run["checkpoints"][0]["state"]["inventory"]["registered_receipt_ids"] = ["R1"]
    elif kind == "return":
        for point in [run["checkpoints"][-1], run["at_horizon"], run["at_end"]]:
            point["state"]["workers"][0]["waiting_since"] = 0
    else:
        field = "inventory_claim" if kind == "claims" else "resource_id"
        for e in run["events"]:
            if field == "inventory_claim":
                e["inventory_claim"] = e["released_claim_id"] = None
            else:
                e[field] = None
        for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
            if field == "inventory_claim":
                point["state"]["inventory"]["claims"] = []
                point["state"]["inventory"]["claim_generation"] = 0
            else:
                point["state"]["leases"] = [
                    row for row in point["state"]["leases"] if not row[0].startswith("receipt:")
                ]
