"""Transient receipt authority cannot be hidden between 0s and 30s captures."""

from bisect import bisect_right
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_transport import read_receipt_run, write_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def _settle_envelope(run: dict[str, Any]) -> None:
    run["events"].sort(key=lambda event: (event["tick"], event["seq"]))
    revision = 0
    for seq, event in enumerate(run["events"]):
        event["seq"] = seq
        if event["delta"] is not None:
            revision += 1
            event["delta"]["revision"] = revision
    ticks = [event["tick"] for event in run["events"]]
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        point["last_seq"] = bisect_right(ticks, point["tick"]) - 1
        point["state"]["stock"]["revision"] = sum(
            e["delta"] is not None for e in run["events"] if e["tick"] <= point["tick"]
        )
        point["state_hash"] = sha256_hex(point["state"])


def _excursion(run: dict[str, Any]) -> None:
    pick = next(e for e in run["events"] if e["kind"] == "picked")
    assert pick["tick"] == 29_000_000
    forward, backward = deepcopy(pick), deepcopy(pick)
    for event, tick, suffix in ((forward, 24_000_001, "out"), (backward, 25_000_000, "back")):
        event.update(kind="packed", tick=tick)
        event["delta"].update(operation="transfer", transaction_id=f"unauthorized:{suffix}")
    backward["delta"]["before"], backward["delta"]["after"] = (
        backward["delta"]["after"],
        backward["delta"]["before"],
    )
    run["events"].extend((forward, backward))


def _wrong_service_actor(run: dict[str, Any]) -> None:
    event = next(
        e
        for e in run["events"]
        if e["kind"] == "operation_completed" and e["operation"]["kind"] == "receipt_service"
    )
    assert event["tick"] == 12_000_000 and event["actor_id"] == "R01"
    event["actor_id"] = "R02"


def _early_buffer_pickup(run: dict[str, Any]) -> None:
    for event in run["events"]:
        if event["kind"] == "receipt_buffer_picked" or (
            event["kind"] == "receipt_resource_released"
            and event["resource_id"] == "receipt:place:receipt-buffer"
        ):
            assert event["tick"] == 17_000_000
            event["tick"] = 16_000_000


@pytest.mark.parametrize("forgery", ["claim_excursion", "service_actor", "buffer_pickup"])
def test_transient_authority_forgery_is_rejected(tmp_path: Path, forgery: str) -> None:
    inputs, outcome = sample()
    run = build_receipt_run(inputs, outcome)
    mutations = {
        "claim_excursion": _excursion,
        "service_actor": _wrong_service_actor,
        "buffer_pickup": _early_buffer_pickup,
    }
    mutations[forgery](run)
    _settle_envelope(run)
    with pytest.raises(ValueError):
        write_receipt_run(run, tmp_path, inputs=inputs.frozen_bytes)
        read_receipt_run(tmp_path)
