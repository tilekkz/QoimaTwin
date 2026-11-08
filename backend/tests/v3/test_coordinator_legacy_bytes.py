"""Pre-change compatibility byte controls, not engine-derived numeric acceptance expectations."""

import json
from pathlib import Path

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.run_values import wire_value
from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_light_flow_fixtures import hand_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


@pytest.mark.parametrize("kind", ["light", "receipt", "whole"])
def test_legacy_native_and_event_bytes_match_verified_preimages(kind: str) -> None:
    if kind == "light":
        outcome = LightFlowEngine(hand_profile(), receipt_conveyor()).run(
            300 * SECOND, 400 * SECOND
        )
    elif kind == "receipt":
        outcome = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor()).run(
            300 * SECOND, 400 * SECOND
        )
    else:
        outcome = WholeFlowEngine(whole_hand_profile(), receipt_conveyor()).run(
            60 * SECOND, 100 * SECOND
        )
    expected = json.loads(Path(__file__).with_name("coordinator_legacy_bytes.json").read_bytes())[
        "cases"
    ][kind]
    assert sha256_hex(wire_value(outcome.events)) == expected["events_sha256"]
    assert sha256_hex(wire_value(outcome)) == expected["outcome_sha256"]
