"""The C journal replays authoritative stock commands, never snapshot bootstrap."""

from dataclasses import replace
from functools import lru_cache

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile
from app.v3.coordinator_run_inventory import InventoryJournal
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


@lru_cache(maxsize=1)
def inventory_case() -> tuple[CoordinatorProfile, CoordinatorOutcome]:
    profile = multi_profile()
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(300 * SECOND, 400 * SECOND)
    return profile, outcome


def test_all_captures_match_one_stock_authority_and_exact_claim_generation() -> None:
    profile, outcome = inventory_case()
    journal, cursor = InventoryJournal(profile), 0
    captures = sorted(
        (*outcome.checkpoints, outcome.at_horizon, outcome.at_end),
        key=lambda row: (row.tick, row.last_seq),
    )
    for state in captures:
        while cursor <= state.last_seq:
            journal.apply(outcome.events[cursor])
            cursor += 1
        journal.check(state)
    assert sum(n for _, n in outcome.at_end.balance.shipped_units_by_sku) == 6
    assert outcome.at_end.inventory.claims == ()
    assert outcome.at_end.inventory.claim_generation == 4


def test_missing_consumed_unit_claim_fact_is_not_inferred_from_pick_delta() -> None:
    profile, outcome = inventory_case()
    journal = InventoryJournal(profile)
    with pytest.raises(ValueError, match="claim"):
        for event in outcome.events:
            if event.kind != "inventory_claim_released":
                journal.apply(event)


def test_stock_delta_cannot_substitute_declared_placement_or_owner() -> None:
    profile, outcome = inventory_case()
    journal = InventoryJournal(profile)
    for event in outcome.events:
        if event.kind != "picked":
            journal.apply(event)
            continue
        assert event.delta is not None
        after = list(event.delta.after)
        target = next(i for i, row in enumerate(after) if row.container.recipe.kind == "carrier")
        after[target] = replace(
            after[target], container=replace(after[target].container, owner_id="unvisited")
        )
        with pytest.raises(ValueError, match="delta"):
            journal.apply(replace(event, delta=replace(event.delta, after=tuple(after))))
        return
    pytest.fail("Hand fixture must pick its declared units")


def test_snapshot_cannot_drop_registry_generation_or_clone_received_units() -> None:
    profile, outcome = inventory_case()
    journal = InventoryJournal(profile)
    for event in outcome.events:
        journal.apply(event)
    changed = replace(outcome.at_end.inventory, claim_generation=0)
    with pytest.raises(ValueError, match="inventory"):
        journal.check(replace(outcome.at_end, inventory=changed))
