"""Capacity uses one current mass projection; no engine or source compilation."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3 import stock_ledger
from app.v3.receipt_flow_models import ReceiptOffer
from app.v3.relocation_run_inventory import RelocationInventory
from app.v3.relocation_run_resources import RelocationResources
from app.v3.stock_models import (
    Container,
    ContainerContents,
    Placement,
    StockSeed,
    UnitLocation,
    UnitToken,
)
from app.v3.stock_receipts import ReceiptDefinition
from app.v3.stock_state import contents_view
from tests.v3.test_relocation_runtime_fixtures import relocation_hand


def resources() -> RelocationResources:
    profile = replace(relocation_hand(standard=False), jobs=())
    world = profile.coordinator.world
    flow, original = world.receipts.flow, world.receipts.flow.stock
    seed = StockSeed(
        tuple(
            replace(u, unit_id=f"{i}:{u.unit_id}", origin_hu=f"HU{i}")
            for i in range(3)
            for u in original.units
        ),
        tuple(
            replace(original.containers[0], container_id=f"HU{i}", owner_id=f"s{i}")
            for i in range(3)
        ),
        (*tuple(replace(original.owners[0], owner_id=f"s{i}") for i in range(3)), *original.owners),
    )
    world = replace(world, receipts=replace(world.receipts, flow=replace(flow, stock=seed)))
    places = tuple(replace(profile.places[0], owner_id=f"s{i}") for i in range(3))
    profile = replace(profile, coordinator=replace(profile.coordinator, world=world), places=places)
    return RelocationResources(profile, RelocationInventory(profile, ()), (), ())


def test_capacity_does_not_repeat_full_contents_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = resources()
    original = contents_view
    scans: list[int] = []

    def observed(
        container: Container,
        locations: dict[str, UnitLocation],
        tokens: dict[str, UnitToken],
    ) -> ContainerContents:
        scans.append(len(locations))
        return original(container, locations, tokens)

    monkeypatch.setattr(stock_ledger, "contents_view", observed)
    journal.check_capacity()
    assert scans == []  # Old path performs three independent scans of all 72 locations.


@pytest.mark.parametrize("limit", [F("2.82"), F("2.82") - F(1, 10**12)])
def test_module_limit_uses_exact_current_gross_mass(limit: F) -> None:
    journal = resources()
    journal.extension = replace(
        journal.extension,
        places=tuple(replace(p, module_max_gross_kg=limit) for p in journal.extension.places),
    )
    if limit == F("2.82"):
        journal.check_capacity()  # Three * (.1 wrapper + 24 * .035 unit).
    else:
        with pytest.raises(ValueError, match="occupants and promises"):
            journal.check_capacity()


def test_pick_reduces_actual_module_mass_without_using_initial_mass() -> None:
    journal = resources()
    journal.check_capacity()
    state = journal.inventory.ledger
    carrier = next(c for c in state.snapshot().containers if c.recipe.kind == "carrier")
    state.pick("pick", 0, "HU0", carrier.container_id, (Placement("0:U1", (F(0), F(0), F(0))),))
    journal.extension = replace(
        journal.extension,
        places=tuple(replace(p, module_max_gross_kg=F("2.785")) for p in journal.extension.places),
    )
    journal.check_capacity()  # 3*.94 - .035; the picked unit is now outside this module.


@pytest.mark.parametrize("count,mass", [(3, F(4)), (4, F("3.76") - F(1, 10**12))])
def test_receipt_promises_still_consume_count_and_mass(count: int, mass: F) -> None:
    journal = resources()
    journal.extension = replace(
        journal.extension,
        places=tuple(
            replace(p, module_max_hus=count, module_max_gross_kg=mass)
            for p in (
                *journal.extension.places,
                replace(journal.extension.places[0], owner_id="target"),
            )
        ),
    )
    journal.inventory.receipts["R"] = ReceiptOffer(
        ReceiptDefinition("R", "INCOMING", "SKU1", "NEWLOT", 24), 0, "IN", "target"
    )
    journal.check_capacity()  # An unreserved future offer is not yet an occupant.
    journal.leases["receipt:place:target"] = "R"
    with pytest.raises(ValueError, match="occupants and promises"):
        journal.check_capacity()
