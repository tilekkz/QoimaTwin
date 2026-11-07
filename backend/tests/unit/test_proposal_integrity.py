"""Cross-reference and observation-boundary checks beyond structural JSON Schema."""

import copy
from typing import Any

import pytest

from app.exporter.proposal import validate_proposal
from tests.unit.test_proposal_export import proposal as proposal


@pytest.mark.parametrize("fault", ["watermark", "identity", "cargo", "action"])
def test_proposal_rejects_incoherent_references(proposal: dict[str, Any], fault: str) -> None:
    altered = copy.deepcopy(proposal)
    if fault == "watermark":
        altered["snapshots"][1]["last_seq"] -= 1
    elif fault == "identity":
        altered["input_hashes"] = {**altered["input_hashes"], "layout": "0" * 64}
    elif fault == "cargo":
        event = next(e for e in altered["events"] if e["kind"] == "cell_moved")
        event["payload"]["cargo_id"] = "UNKNOWN_CARGO"
    else:
        event = next(e for e in altered["events"] if e["kind"] == "actor_state_changed")
        event["payload"]["action_id"] = "UNKNOWN_ACTION"
    with pytest.raises(ValueError, match=fault):
        validate_proposal(altered)
