"""Rehashed histories still need real arrivals, reservations and intact original wrappers."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.interface import Json
from app.v3.whole_run import build_whole_run, validate_whole_run
from tests.v3.test_whole_run_fixtures import sample


def _reindex(run: Json) -> None:
    for seq, event in enumerate(run["events"]):
        event["seq"] = seq
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        point["last_seq"] = sum(e["tick"] <= point["tick"] for e in run["events"]) - 1
        point["state_hash"] = sha256_hex(point["state"])


def test_unknown_whole_event_kind_cannot_hide_in_a_valid_view() -> None:
    run = build_whole_run(*sample())
    next(e for e in run["events"] if e["kind"] == "whole_state_changed")["kind"] = "invented"
    with pytest.raises(ValueError, match=r"kind|event"):
        validate_whole_run(run)


def test_removed_arrival_event_is_rejected_after_watermarks_are_repaired() -> None:
    run = build_whole_run(*sample())
    run["events"] = [e for e in run["events"] if e["kind"] != "whole_arrived"]
    _reindex(run)
    with pytest.raises(ValueError, match=r"arrival|arrived"):
        validate_whole_run(run)


def test_intact_wrapper_cannot_acquire_a_forged_parcel_seal() -> None:
    run = deepcopy(build_whole_run(*sample()))
    handover = next(e for e in run["events"] if e["kind"] == "whole_shipped")
    handover["delta"]["after"][0]["container"]["sealed_for"] = "W1"
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        if point["tick"] >= handover["tick"]:
            next(c for c in point["state"]["stock"]["containers"] if c["container_id"] == "HU1")[
                "sealed_for"
            ] = "W1"
    _reindex(run)
    with pytest.raises(ValueError, match=r"seal|wrapper|intact"):
        validate_whole_run(run)


def test_claim_and_resource_journals_cannot_be_deleted_together() -> None:
    run = build_whole_run(*sample())
    run["events"] = [
        e
        for e in run["events"]
        if not e["kind"].startswith(("inventory_claim_", "whole_resource_"))
    ]
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        point["state"]["inventory"].update(claims=[], claim_generation=0)
        point["state"]["leases"] = []
    _reindex(run)
    with pytest.raises(ValueError, match=r"fact|resource|claim"):
        validate_whole_run(run)


def test_distinct_atomic_transactions_cannot_reuse_one_identity() -> None:
    run = build_whole_run(*sample())
    deltas = [e["delta"] for e in run["events"] if e["delta"] is not None]
    deltas[1]["transaction_id"] = deltas[0]["transaction_id"]
    with pytest.raises(ValueError, match="transaction"):
        validate_whole_run(run)


def test_returned_view_cannot_reassign_history_to_another_eligible_actor() -> None:
    run = build_whole_run(*sample())
    returned = next(e for e in run["events"] if e["kind"] == "whole_returned")
    returned["whole_order"]["actor_id"] = "S02"
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        if point["tick"] >= returned["tick"]:
            point["state"]["whole_orders"][0]["actor_id"] = "S02"
    _reindex(run)
    with pytest.raises(ValueError, match=r"actor|assignment|resource"):
        validate_whole_run(run)


def test_transient_whole_view_cannot_borrow_a_second_actor_between_captures() -> None:
    run = build_whole_run(*sample())
    changed = next(e for e in run["events"] if e["kind"] == "whole_state_changed")
    changed["actor_id"] = "S02"
    changed["whole_order"]["actor_id"] = "S02"
    with pytest.raises(ValueError, match=r"actor|assignment"):
        validate_whole_run(run)
