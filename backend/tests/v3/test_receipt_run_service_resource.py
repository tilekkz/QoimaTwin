"""A service wholly between cadence checkpoints must still acquire its finite port."""

from bisect import bisect_right

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.receipt_run import build_receipt_run, validate_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def test_deleted_port_reservation_cannot_hide_between_captured_states() -> None:
    run = build_receipt_run(*sample(), validate=False)
    run["events"] = [
        e for e in run["events"] if not (e["resource_id"] or "").startswith("receipt:port:")
    ]
    for seq, event in enumerate(run["events"]):
        event["seq"] = seq
    ticks = [e["tick"] for e in run["events"]]
    for point in [*run["checkpoints"], run["at_horizon"], run["at_end"]]:
        point["last_seq"] = bisect_right(ticks, point["tick"]) - 1
        point["state"]["leases"] = [
            r for r in point["state"]["leases"] if not r[0].startswith("receipt:port:")
        ]
        point["state_hash"] = sha256_hex(point["state"])
    with pytest.raises(ValueError):
        validate_receipt_run(run)
